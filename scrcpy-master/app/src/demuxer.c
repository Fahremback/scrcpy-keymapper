#include "demuxer.h"

#include <inttypes.h>
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/time.h>
#include <unistd.h>

#include "common.h"
#include "compat.h"
#include "events.h"
#include "options.h"
#include "packet_merger.h"
#include "util/binary.h"
#include "util/log.h"
#include "util/net.h"

/**
 * Byte                Content
 * -----------------------------------
 * [0]                 media packet flag
 * [0]                 session packet flag
 * [0]                 config packet flag
 * [0]                 key frame flag
 * [0..7]              PTS (62 bits)
 * [8..11]             packet size (32 bits)
 *
 * The most significant bit of byte 0 is the media packet flag:
 *  - 0: session packet
 *  - 1: media packet
 *
 * For a session packet:
 *  - the next bit is the client resized flag (R)
 *  - the remaining bits of the first 4 bytes are unused (must be 0)
 *  - the next 4 bytes contain the video width (32 bits)
 *  - the next 4 bytes contain the video height (32 bits)
 *
 *  byte 0   byte 1   byte 2   byte 3
 * 00000000 00000000 00000000 0000000R
 * ^<------------------------------->^
 * |               padding           |
 *  `- session packet flag            `- client resized flag
 *
 *  byte 4   byte 5   byte 6   byte 7   byte 8   byte 9   byte 10  byte 11
 * ........ ........ ........ ........ ........ ........ ........ ........
 * <---------------------------------> <--------------------------------->
 *             video width                         video height
 *
 * For a media packet:
 *  - the next bit is the config packet flag
 *  - the next bit is the key frame flag
 *  - the remaining 6 bits of byte 0 and the next 7 bytes contain the PTS (62 bits)
 *  - the next 4 bytes contain the packet size (32 bits)
 *
 *  byte 0   byte 1   byte 2   byte 3   byte 4   byte 5   byte 6   byte 7
 * 1CK..... ........ ........ ........ ........ ........ ........ ........
 * ^^<------------------------------------------------------------------>
 * ||                                PTS
 * | `- key frame flag
 *  `-- config packet flag
 *
 *  byte 8   byte 9   byte 10  byte 11
 * ........ ........ ........ ........
 * <--------------------------------->
 *             packet size
 */

#define SC_PACKET_HEADER_SIZE 12

#define SC_PACKET_FLAG_MEDIA (~((uint64_t) 1 << 63))
#define SC_PACKET_FLAG_CONFIG ((uint64_t) 1 << 62)
#define SC_PACKET_FLAG_KEY_FRAME ((uint64_t) 1 << 61)

#define SC_PACKET_PTS_MASK (SC_PACKET_FLAG_KEY_FRAME - 1)

static enum AVCodecID
sc_demuxer_to_avcodec_id(uint32_t codec_id) {
    switch (codec_id) {
        case SC_CODEC_H264:
            return AV_CODEC_ID_H264;
        case SC_CODEC_H265:
            return AV_CODEC_ID_HEVC;
        case SC_CODEC_AV1:
#ifdef SCRCPY_LAVF_HAS_AV1
            return AV_CODEC_ID_AV1;
#else
            LOGE("AV1 not supported by this FFmpeg version");
            return AV_CODEC_ID_NONE;
#endif
        case SC_CODEC_VP8:
            return AV_CODEC_ID_VP8;
        case SC_CODEC_VP9:
            return AV_CODEC_ID_VP9;
        case SC_CODEC_OPUS:
            return AV_CODEC_ID_OPUS;
        case SC_CODEC_AAC:
            return AV_CODEC_ID_AAC;
        case SC_CODEC_FLAC:
            return AV_CODEC_ID_FLAC;
        case SC_CODEC_RAW:
            return AV_CODEC_ID_PCM_S16LE;
        default:
            LOGE("Unknown codec id 0x%08" PRIx32, codec_id);
            return AV_CODEC_ID_NONE;
    }
}

static inline bool
sc_demuxer_is_session(const uint8_t buf[static SC_PACKET_HEADER_SIZE]) {
    return !(buf[0] & 0x80);
}

static void
sc_demuxer_parse_session(const uint8_t buf[static SC_PACKET_HEADER_SIZE],
                         struct sc_stream_session *session) {
    assert(sc_demuxer_is_session(buf));
    session->video.client_resized = buf[3] & 1;
    session->video.width = sc_read32be(&buf[4]);
    session->video.height = sc_read32be(&buf[8]);
}

static void
sc_demuxer_parse_media(const uint8_t buf[static SC_PACKET_HEADER_SIZE],
                       AVPacket *packet) {
    assert(!sc_demuxer_is_session(buf));
    uint64_t pts_flags = sc_read64be(buf);
    if (pts_flags & SC_PACKET_FLAG_CONFIG) {
        packet->flags |= AV_PKT_FLAG_CORRUPT;
    }
    if (pts_flags & SC_PACKET_FLAG_KEY_FRAME) {
        packet->flags |= AV_PKT_FLAG_KEY;
    }
    uint64_t pts = pts_flags & SC_PACKET_PTS_MASK;
    packet->pts = pts == SC_PACKET_PTS_MASK ? AV_NOPTS_VALUE : (int64_t) pts;
    packet->size = sc_read32be(&buf[8]);
}

static bool
sc_demuxer_recv_codec_id(struct sc_demuxer *demuxer, uint32_t *codec_id) {
    uint8_t data[4];
    ssize_t r = net_recv_all(demuxer->socket, data, 4);
    if (r <= 0) {
        return false;
    }

    *codec_id = sc_read32be(data);
    return true;
}

static inline bool
sc_demuxer_recv_header(struct sc_demuxer *demuxer,
                       uint8_t buf[static SC_PACKET_HEADER_SIZE]) {
    ssize_t r = net_recv_all(demuxer->socket, buf, SC_PACKET_HEADER_SIZE);
    if (r <= 0) {
        return false;
    }

    return true;
}

static bool
sc_demuxer_recv_packet(struct sc_demuxer *demuxer,
                       uint8_t header[static SC_PACKET_HEADER_SIZE],
                       AVPacket *packet,
                       struct sc_stream_session *session) {
    bool is_session = sc_demuxer_is_session(header);
    if (is_session) {
        sc_demuxer_parse_session(header, session);
        return true;
    }

    sc_demuxer_parse_media(header, packet);

    assert(packet->size);
    if (av_new_packet(packet, packet->size)) {
        LOG_OOM();
        return false;
    }

    ssize_t r = net_recv_all(demuxer->socket, packet->data, packet->size);
    if (r <= 0) {
        av_packet_unref(packet);
        return false;
    }

    packet->dts = packet->pts;
    return true;
}

static int
run_demuxer(void *data) {
    struct sc_demuxer *demuxer = data;

    enum sc_demuxer_status status = SC_DEMUXER_STATUS_ERROR;

    uint32_t raw_codec_id;
    bool ok = sc_demuxer_recv_codec_id(demuxer, &raw_codec_id);
    if (!ok) {
        LOGE("Demuxer '%s': stream disabled due to connection error",
             demuxer->name);
        goto end;
    }

    if (raw_codec_id == 0) {
        LOGW("Demuxer '%s': stream explicitly disabled by the device",
             demuxer->name);
        sc_packet_source_sinks_disable(&demuxer->packet_source);
        status = SC_DEMUXER_STATUS_DISABLED;
        goto end;
    }

    if (raw_codec_id == 1) {
        LOGE("Demuxer '%s': stream configuration error on the device",
             demuxer->name);
        goto end;
    }

    enum AVCodecID codec_id = sc_demuxer_to_avcodec_id(raw_codec_id);
    if (codec_id == AV_CODEC_ID_NONE) {
        LOGE("Demuxer '%s': stream disabled due to unsupported codec",
             demuxer->name);
        sc_packet_source_sinks_disable(&demuxer->packet_source);
        goto end;
    }

    const AVCodec *codec = avcodec_find_decoder(codec_id);
    if (!codec) {
        LOGE("Demuxer '%s': stream disabled due to missing decoder",
             demuxer->name);
        sc_packet_source_sinks_disable(&demuxer->packet_source);
        goto end;
    }

    AVCodecContext *codec_ctx = avcodec_alloc_context3(codec);
    if (!codec_ctx) {
        LOG_OOM();
        goto end;
    }

    // === EXTREME LOW LATENCY DECODE FLAGS ===
    codec_ctx->flags |= AV_CODEC_FLAG_LOW_DELAY;
    codec_ctx->flags2 |= AV_CODEC_FLAG2_FAST;
    codec_ctx->skip_loop_filter = AVDISCARD_ALL;

    uint8_t header[SC_PACKET_HEADER_SIZE];
    struct sc_stream_session session_data;

    struct sc_stream_session *session = NULL;
    if (codec->type == AVMEDIA_TYPE_VIDEO) {
        bool ok = sc_demuxer_recv_header(demuxer, header);
        if (!ok) {
            goto finally_free_context;
        }

        if (!sc_demuxer_is_session(header)) {
            LOGE("Unexpected packet (not a session header)");
            goto finally_free_context;
        }

        session = &session_data;
        sc_demuxer_parse_session(header, session);

        if (!session_data.video.width || !session_data.video.height) {
            LOGE("Invalid session video size: %" PRIu32 "x%" PRIu32,
                 session_data.video.width, session_data.video.height);
            goto finally_free_context;
        }

        codec_ctx->width = session_data.video.width;
        codec_ctx->height = session_data.video.height;
        codec_ctx->pix_fmt = AV_PIX_FMT_YUV420P;
    } else {
        codec_ctx->ch_layout = (AVChannelLayout) AV_CHANNEL_LAYOUT_STEREO;
        codec_ctx->sample_rate = 48000;

        if (raw_codec_id == SC_CODEC_FLAC) {
            codec_ctx->sample_fmt = AV_SAMPLE_FMT_S16;
        }
    }

    if (avcodec_open2(codec_ctx, codec, NULL) < 0) {
        LOGE("Demuxer '%s': could not open codec", demuxer->name);
        goto finally_free_context;
    }

    if (!sc_packet_source_sinks_open(&demuxer->packet_source, codec_ctx,
                                     session)) {
        goto finally_free_context;
    }

    bool is_h26x = raw_codec_id == SC_CODEC_H264
                || raw_codec_id == SC_CODEC_H265;
    bool is_audio = codec->type == AVMEDIA_TYPE_AUDIO;
    bool must_merge_config_packet = is_h26x || is_audio;

    struct sc_packet_merger merger;
    if (must_merge_config_packet) {
        sc_packet_merger_init(&merger);
    }

    AVPacket *packet = av_packet_alloc();
    if (!packet) {
        LOG_OOM();
        goto finally_close_sinks;
    }

    for (;;) {
        bool ok = sc_demuxer_recv_header(demuxer, header);
        if (!ok) {
            status = SC_DEMUXER_STATUS_EOS;
            break;
        }

        struct sc_stream_session new_session;
        ok = sc_demuxer_recv_packet(demuxer, header, packet, &new_session);
        if (!ok) {
            status = SC_DEMUXER_STATUS_EOS;
            break;
        }

        if (sc_demuxer_is_session(header)) {
            ok = sc_packet_source_sinks_push_session(&demuxer->packet_source,
                                                     &new_session);
            if (!ok) {
                break;
            }
            continue;
        }

        if (must_merge_config_packet) {
            ok = sc_packet_merger_merge(&merger, packet);
            if (!ok) {
                av_packet_unref(packet);
                break;
            }
        }

        ok = sc_packet_source_sinks_push(&demuxer->packet_source, packet);
        av_packet_unref(packet);
        if (!ok) {
            break;
        }
    }

    LOGD("Demuxer '%s': end of frames", demuxer->name);

    if (must_merge_config_packet) {
        sc_packet_merger_destroy(&merger);
    }

    av_packet_free(&packet);
finally_close_sinks:
    sc_packet_source_sinks_close(&demuxer->packet_source);
finally_free_context:
    avcodec_free_context(&codec_ctx);
end:
    demuxer->cbs->on_ended(demuxer, status, demuxer->cbs_userdata);
    return 0;
}

void
sc_demuxer_init(struct sc_demuxer *demuxer, const char *name,
                sc_socket socket, const struct sc_demuxer_callbacks *cbs,
                void *cbs_userdata) {
    assert(name);
    demuxer->name = name;
    demuxer->socket = socket;
    sc_packet_source_init(&demuxer->packet_source);
    demuxer->cbs = cbs;
    demuxer->cbs_userdata = cbs_userdata;
}

bool
sc_demuxer_start(struct sc_demuxer *demuxer) {
    LOGD("Starting demuxer '%s' thread", demuxer->name);

    bool ok = sc_thread_create(&demuxer->thread, run_demuxer,
                               "scrcpy-demuxer", demuxer);
    if (!ok) {
        LOGE("Demuxer '%s': could not start thread", demuxer->name);
        return false;
    }
    return true;
}

void
sc_demuxer_join(struct sc_demuxer *demuxer) {
    sc_thread_join(&demuxer->thread, NULL);
}

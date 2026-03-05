#include "decoder.h"

#include <errno.h>
#include <libavcodec/packet.h>
#include <libavutil/avutil.h>

#include "util/log.h"

/** Downcast packet_sink to decoder */
#define DOWNCAST(SINK) container_of(SINK, struct sc_decoder, packet_sink)

static bool sc_decoder_open(struct sc_decoder *decoder, AVCodecContext *ctx) {
  decoder->frame = av_frame_alloc();
  if (!decoder->frame) {
    LOG_OOM();
    return false;
  }

  decoder->sw_frame = av_frame_alloc();
  if (!decoder->sw_frame) {
    av_frame_free(&decoder->frame);
    LOG_OOM();
    return false;
  }

  if (!sc_frame_source_sinks_open(&decoder->frame_source, ctx)) {
    av_frame_free(&decoder->sw_frame);
    av_frame_free(&decoder->frame);
    return false;
  }

  decoder->ctx = ctx;

  return true;
}

static void sc_decoder_close(struct sc_decoder *decoder) {
  sc_frame_source_sinks_close(&decoder->frame_source);
  av_frame_free(&decoder->sw_frame);
  av_frame_free(&decoder->frame);
}

static bool sc_decoder_push(struct sc_decoder *decoder,
                            const AVPacket *packet) {
  bool is_config = packet->pts == AV_NOPTS_VALUE;
  if (is_config) {
    // nothing to do
    return true;
  }

  int ret = avcodec_send_packet(decoder->ctx, packet);
  if (ret < 0 && ret != AVERROR(EAGAIN)) {
    LOGE("Decoder '%s': could not send video packet: %d", decoder->name, ret);
    return false;
  }

  for (;;) {
    ret = avcodec_receive_frame(decoder->ctx, decoder->frame);
    if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
      break;
    }

    if (ret) {
      LOGE("Decoder '%s', could not receive video frame: %d", decoder->name,
           ret);
      return false;
    }

    bool ok;
    AVFrame *render_frame = decoder->frame;

    // Se o frame é de aceleração de hardware (ex: VRAM D3D11, CUDA, DXVA2),
    // passamos de volta pra RAM do SDL
    if (decoder->frame->format == AV_PIX_FMT_D3D11 ||
        decoder->frame->format == AV_PIX_FMT_CUDA ||
        decoder->frame->format == AV_PIX_FMT_DXVA2_VLD ||
        decoder->frame->hw_frames_ctx != NULL) {

      ret = av_hwframe_transfer_data(decoder->sw_frame, decoder->frame, 0);
      if (ret < 0) {
        LOGE("Decoder '%s': falha ao transferir hw frame para RAM/sw frame: %d",
             decoder->name, ret);
        av_frame_unref(decoder->frame);
        return false;
      }
      render_frame = decoder->sw_frame;
    }

    // a frame was received
    ok = sc_frame_source_sinks_push(&decoder->frame_source, render_frame);

    av_frame_unref(decoder->frame);
    if (render_frame == decoder->sw_frame) {
      av_frame_unref(decoder->sw_frame);
    }

    if (!ok) {
      // Error already logged
      return false;
    }
  }

  return true;
}

static bool sc_decoder_packet_sink_open(struct sc_packet_sink *sink,
                                        AVCodecContext *ctx) {
  struct sc_decoder *decoder = DOWNCAST(sink);
  return sc_decoder_open(decoder, ctx);
}

static void sc_decoder_packet_sink_close(struct sc_packet_sink *sink) {
  struct sc_decoder *decoder = DOWNCAST(sink);
  sc_decoder_close(decoder);
}

static bool sc_decoder_packet_sink_push(struct sc_packet_sink *sink,
                                        const AVPacket *packet) {
  struct sc_decoder *decoder = DOWNCAST(sink);
  return sc_decoder_push(decoder, packet);
}

void sc_decoder_init(struct sc_decoder *decoder, const char *name) {
  decoder->name = name; // statically allocated
  sc_frame_source_init(&decoder->frame_source);

  static const struct sc_packet_sink_ops ops = {
      .open = sc_decoder_packet_sink_open,
      .close = sc_decoder_packet_sink_close,
      .push = sc_decoder_packet_sink_push,
  };

  decoder->packet_sink.ops = &ops;
}

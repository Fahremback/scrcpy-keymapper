#include "keymapper.h"

#include "control_msg.h"
#include "events.h"
#include "input_events.h"
#include "util/log.h"
#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <sys/stat.h>
#ifdef _WIN32
#include <io.h>
#ifndef F_OK
#define F_OK 0
#endif
#define access _access
#else
#include <unistd.h>
#endif

static struct km_state state;

// =====================================================
// Bitmap font 5x7 for A-Z, 0-9, space, _, -, +
// Each char = 7 bytes, each byte = 5 bits (MSB first)
// =====================================================
static const uint8_t FONT_5X7[][7] = {
    // ' ' (32) idx=0
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
    // '0' idx=1
    {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E},
    // '1'
    {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E},
    // '2'
    {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F},
    // '3'
    {0x0E, 0x11, 0x01, 0x06, 0x01, 0x11, 0x0E},
    // '4'
    {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02},
    // '5'
    {0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E},
    // '6'
    {0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E},
    // '7'
    {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08},
    // '8'
    {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E},
    // '9'
    {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C},
    // 'A' idx=11
    {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11},
    // 'B'
    {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E},
    // 'C'
    {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E},
    // 'D'
    {0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E},
    // 'E'
    {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F},
    // 'F'
    {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10},
    // 'G'
    {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0E},
    // 'H'
    {0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11},
    // 'I'
    {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E},
    // 'J'
    {0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C},
    // 'K'
    {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11},
    // 'L'
    {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F},
    // 'M'
    {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11},
    // 'N'
    {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11},
    // 'O'
    {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E},
    // 'P'
    {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10},
    // 'Q'
    {0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D},
    // 'R'
    {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11},
    // 'S'
    {0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E},
    // 'T'
    {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04},
    // 'U'
    {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E},
    // 'V'
    {0x11, 0x11, 0x11, 0x11, 0x0A, 0x0A, 0x04},
    // 'W'
    {0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11},
    // 'X'
    {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11},
    // 'Y'
    {0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04},
    // 'Z'
    {0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F},
};

static int font_char_index(char c) {
  if (c == ' ')
    return 0;
  if (c >= '0' && c <= '9')
    return 1 + (c - '0');
  if (c >= 'A' && c <= 'Z')
    return 11 + (c - 'A');
  if (c >= 'a' && c <= 'z')
    return 11 + (c - 'a');
  return 0; // space for unknown
}

static void km_draw_char(SDL_Renderer *r, int x, int y, char c, int scale) {
  int idx = font_char_index(c);
  const uint8_t *glyph = FONT_5X7[idx];
  for (int row = 0; row < 7; row++) {
    for (int col = 0; col < 5; col++) {
      if (glyph[row] & (0x10 >> col)) {
        SDL_Rect px = {x + col * scale, y + row * scale, scale, scale};
        SDL_RenderFillRect(r, &px);
      }
    }
  }
}

static void km_draw_text(SDL_Renderer *r, int x, int y, const char *text,
                         int scale) {
  for (int i = 0; text[i]; i++) {
    km_draw_char(r, x + i * (6 * scale), y, text[i], scale);
  }
}

static int km_text_width(const char *text, int scale) {
  int len = (int)strlen(text);
  return len > 0 ? len * 6 * scale - scale : 0;
}

// Draw a filled circle using midpoint algorithm
static void km_draw_filled_circle(SDL_Renderer *r, int cx, int cy, int radius) {
  for (int dy = -radius; dy <= radius; dy++) {
    int dx = (int)SDL_sqrt((double)(radius * radius - dy * dy));
    SDL_RenderDrawLine(r, cx - dx, cy + dy, cx + dx, cy + dy);
  }
}

// Draw circle outline
static void km_draw_circle(SDL_Renderer *r, int cx, int cy, int radius) {
  int x = radius, y = 0, err = 1 - radius;
  while (x >= y) {
    SDL_RenderDrawPoint(r, cx + x, cy + y);
    SDL_RenderDrawPoint(r, cx - x, cy + y);
    SDL_RenderDrawPoint(r, cx + x, cy - y);
    SDL_RenderDrawPoint(r, cx - x, cy - y);
    SDL_RenderDrawPoint(r, cx + y, cy + x);
    SDL_RenderDrawPoint(r, cx - y, cy + x);
    SDL_RenderDrawPoint(r, cx + y, cy - x);
    SDL_RenderDrawPoint(r, cx - y, cy - x);
    y++;
    if (err < 0) {
      err += 2 * y + 1;
    } else {
      x--;
      err += 2 * (y - x) + 1;
    }
  }
}

// =====================================================
// Keycode/Mouse name converters
// =====================================================
static SDL_Keycode km_name_to_keycode(const char *name) {
  if (strlen(name) == 1 && name[0] >= 'a' && name[0] <= 'z')
    return SDLK_a + (name[0] - 'a');
  if (strlen(name) == 1 && name[0] >= '0' && name[0] <= '9')
    return SDLK_0 + (name[0] - '0');
  if (!strcmp(name, "space"))
    return SDLK_SPACE;
  if (!strcmp(name, "lshift"))
    return SDLK_LSHIFT;
  if (!strcmp(name, "rshift"))
    return SDLK_RSHIFT;
  if (!strcmp(name, "lctrl"))
    return SDLK_LCTRL;
  if (!strcmp(name, "rctrl"))
    return SDLK_RCTRL;
  if (!strcmp(name, "lalt"))
    return SDLK_LALT;
  if (!strcmp(name, "ralt"))
    return SDLK_RALT;
  if (!strcmp(name, "tab"))
    return SDLK_TAB;
  if (!strcmp(name, "escape") || !strcmp(name, "esc"))
    return SDLK_ESCAPE;
  if (!strcmp(name, "enter") || !strcmp(name, "return"))
    return SDLK_RETURN;
  if (!strcmp(name, "backspace"))
    return SDLK_BACKSPACE;
  if (!strcmp(name, "up"))
    return SDLK_UP;
  if (!strcmp(name, "down"))
    return SDLK_DOWN;
  if (!strcmp(name, "left"))
    return SDLK_LEFT;
  if (!strcmp(name, "right"))
    return SDLK_RIGHT;
  if (!strcmp(name, "f1"))
    return SDLK_F1;
  if (!strcmp(name, "f2"))
    return SDLK_F2;
  if (!strcmp(name, "f3"))
    return SDLK_F3;
  if (!strcmp(name, "f4"))
    return SDLK_F4;
  if (!strcmp(name, "f5"))
    return SDLK_F5;
  if (!strcmp(name, "f6"))
    return SDLK_F6;
  if (!strcmp(name, "f7"))
    return SDLK_F7;
  if (!strcmp(name, "f8"))
    return SDLK_F8;
  if (!strcmp(name, "f9"))
    return SDLK_F9;
  if (!strcmp(name, "f10"))
    return SDLK_F10;
  if (!strcmp(name, "f11"))
    return SDLK_F11;
  if (!strcmp(name, "capslock"))
    return SDLK_CAPSLOCK;
  if (!strcmp(name, "insert"))
    return SDLK_INSERT;
  if (!strcmp(name, "delete"))
    return SDLK_DELETE;
  if (!strcmp(name, "home"))
    return SDLK_HOME;
  if (!strcmp(name, "end"))
    return SDLK_END;
  if (!strcmp(name, "pageup"))
    return SDLK_PAGEUP;
  if (!strcmp(name, "pagedown"))
    return SDLK_PAGEDOWN;
  return SDLK_UNKNOWN;
}

static uint8_t km_name_to_mouse(const char *name) {
  if (!strcmp(name, "left"))
    return SDL_BUTTON_LEFT;
  if (!strcmp(name, "right"))
    return SDL_BUTTON_RIGHT;
  if (!strcmp(name, "middle"))
    return SDL_BUTTON_MIDDLE;
  return 0;
}

// =====================================================
// Config load/save
// =====================================================
static void km_run_reload(void *userdata) {
  (void)userdata;
  km_reload_config();
}
static void km_run_toggle_edit(void *userdata) {
  (void)userdata;
  km_toggle_edit();
}
static void km_run_toggle_overlay(void *userdata) {
  (void)userdata;
  km_toggle_overlay();
}
static void km_run_toggle_fps(void *userdata) {
  (void)userdata;
  km_toggle_fps();
}
static void km_run_opac_up(void *userdata) {
  (void)userdata;
  km_adjust_opacity(0.1f);
}
static void km_run_opac_down(void *userdata) {
  (void)userdata;
  km_adjust_opacity(-0.1f);
}

static uint32_t km_ipc_timer_cb(uint32_t interval, void *param) {
  (void)param;
  struct stat st;

  // Monitor keymap.cfg
  if (stat("C:/Users/fahre/Desktop/scrcpy-win64-v3.3.4/keymap.cfg", &st) == 0) {
    static time_t last_cfg_time = 0;
    if (last_cfg_time == 0)
      last_cfg_time = st.st_mtime;
    else if (st.st_mtime > last_cfg_time) {
      last_cfg_time = st.st_mtime;
      sc_post_to_main_thread(km_run_reload, NULL);
    }
  }

  // Monitor keymap.cmd
  if (access("C:/Users/fahre/Desktop/scrcpy-win64-v3.3.4/keymap.cmd", F_OK) ==
      0) {
    FILE *cmd_f =
        fopen("C:/Users/fahre/Desktop/scrcpy-win64-v3.3.4/keymap.cmd", "r");
    if (cmd_f) {
      char cmd_str[64];
      if (fgets(cmd_str, sizeof(cmd_str), cmd_f)) {
        if (strncmp(cmd_str, "TOGGLE_EDIT", 11) == 0)
          sc_post_to_main_thread(km_run_toggle_edit, NULL);
        else if (strncmp(cmd_str, "TOGGLE_OVERLAY", 14) == 0)
          sc_post_to_main_thread(km_run_toggle_overlay, NULL);
        else if (strncmp(cmd_str, "TOGGLE_FPS", 10) == 0)
          sc_post_to_main_thread(km_run_toggle_fps, NULL);
        else if (strncmp(cmd_str, "OPAC_UP", 7) == 0)
          sc_post_to_main_thread(km_run_opac_up, NULL);
        else if (strncmp(cmd_str, "OPAC_DOWN", 9) == 0)
          sc_post_to_main_thread(km_run_opac_down, NULL);
      }
      fclose(cmd_f);
    }
    remove("C:/Users/fahre/Desktop/scrcpy-win64-v3.3.4/keymap.cmd");
  }
  return interval;
}

void km_init(void) {
  if (state.loaded)
    return;
  state.loaded = true;
  state.count = 0;
  state.edit_mode = false;
  state.fps_mode = false;
  state.show_overlay = true;
  state.opacity = 0.6f;
  state.dragging = -1;
  state.selected = -1;

  SDL_AddTimer(100, km_ipc_timer_cb, NULL);

  const char *paths[] = {
      "keymap.cfg", "C:/Users/fahre/Desktop/scrcpy-win64-v3.3.4/keymap.cfg",
      NULL};
  FILE *f = NULL;
  for (int i = 0; paths[i]; i++) {
    f = fopen(paths[i], "r");
    if (f) {
      LOGI("Keymapper: loaded config from %s", paths[i]);
      break;
    }
  }
  if (!f) {
    LOGW("Keymapper: keymap.cfg not found");
    return;
  }

  char line[512], name_str[32], type_str[16];
  int pid = 1;
  float xp, yp;
  while (fgets(line, sizeof(line), f) && state.count < KM_MAX_BINDINGS) {
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == '#' || line[0] == '\0')
      continue;

    struct km_binding *b = &state.bindings[state.count];
    memset(b, 0, sizeof(*b));
    b->pointer_id = SC_POINTER_ID_GENERIC_FINGER + pid++;

    if (sscanf(line, "%15s %31s %f %f", type_str, name_str, &xp, &yp) < 4)
      continue;
    b->x_pct = xp;
    b->y_pct = yp;

    if (!strcmp(type_str, "KEY")) {
      b->type = KM_TYPE_KEY;
      b->keycode = km_name_to_keycode(name_str);
      if (b->keycode == SDLK_UNKNOWN)
        continue;
      state.count++;
    } else if (!strcmp(type_str, "MOUSE")) {
      b->type = KM_TYPE_MOUSE;
      b->mouse_button = km_name_to_mouse(name_str);
      if (b->mouse_button == 0)
        continue;
      state.count++;
    } else if (!strcmp(type_str, "AIM")) {
      b->type = KM_TYPE_AIM;
      b->keycode = km_name_to_keycode(name_str);
      state.count++;
    } else if (!strcmp(type_str, "DPAD")) {
      b->type = KM_TYPE_DPAD;
      b->keycode =
          km_name_to_keycode(name_str); // placeholder, WASD is hardcoded
      float radius = 0.08f;
      sscanf(line, "%*s %*s %*f %*f %f", &radius);
      b->dpad_radius = radius;
      state.count++;
    } else if (!strcmp(type_str, "SCROLL")) {
      b->type = KM_TYPE_SCROLL;
      b->keycode = km_name_to_keycode(name_str);
      state.count++;
    } else if (!strcmp(type_str, "MACRO")) {
      b->type = KM_TYPE_MACRO;
      b->keycode = km_name_to_keycode(name_str);
      b->macro_step_count = 0;
      // Parse macro steps after the 4th field: "x,y,delay;x,y,delay;..."
      char *steps_start = line;
      int field = 0;
      while (*steps_start && field < 4) {
        if (*steps_start == ' ' || *steps_start == '\t') {
          while (*steps_start == ' ' || *steps_start == '\t')
            steps_start++;
          field++;
        } else {
          steps_start++;
        }
      }
      if (*steps_start) {
        char steps_buf[256];
        strncpy(steps_buf, steps_start, sizeof(steps_buf) - 1);
        steps_buf[sizeof(steps_buf) - 1] = '\0';
        char *token = strtok(steps_buf, ";");
        while (token && b->macro_step_count < KM_MAX_MACRO_STEPS) {
          struct km_macro_step *ms = &b->macro_steps[b->macro_step_count];
          if (sscanf(token, "%f,%f,%d", &ms->x_pct, &ms->y_pct,
                     &ms->delay_ms) == 3) {
            b->macro_step_count++;
          }
          token = strtok(NULL, ";");
        }
      }
      state.count++;
    }
  }
  fclose(f);
  LOGI("Keymapper: %d bindings loaded", state.count);
}

void km_save_config(void) {
  FILE *f = fopen("keymap.cfg", "w");
  if (!f) {
    f = fopen("C:/Users/fahre/Desktop/scrcpy-win64-v3.3.4/keymap.cfg", "w");
  }
  if (!f) {
    LOGW("Keymapper: cannot save keymap.cfg");
    return;
  }
  fprintf(f, "# Scrcpy Keymapper Config\n");
  fprintf(f, "# Types: KEY, MOUSE, AIM, DPAD, SCROLL, MACRO\n");
  for (int i = 0; i < state.count; i++) {
    struct km_binding *b = &state.bindings[i];
    // Helper: get lowercase key name
    const char *raw_name =
        (b->type != KM_TYPE_MOUSE) ? SDL_GetKeyName(b->keycode) : "";
    char lname[32];
    int j;
    for (j = 0; raw_name[j] && j < 30; j++)
      lname[j] = (raw_name[j] >= 'A' && raw_name[j] <= 'Z') ? raw_name[j] + 32
                                                            : raw_name[j];
    lname[j] = '\0';
    if (!strcmp(lname, "left shift"))
      strcpy(lname, "lshift");
    else if (!strcmp(lname, "right shift"))
      strcpy(lname, "rshift");
    else if (!strcmp(lname, "left ctrl"))
      strcpy(lname, "lctrl");
    else if (!strcmp(lname, "right ctrl"))
      strcpy(lname, "rctrl");
    else if (!strcmp(lname, "left alt"))
      strcpy(lname, "lalt");
    else if (!strcmp(lname, "right alt"))
      strcpy(lname, "ralt");

    switch (b->type) {
    case KM_TYPE_KEY:
      fprintf(f, "KEY %s %.3f %.3f\n", lname, b->x_pct, b->y_pct);
      break;
    case KM_TYPE_MOUSE: {
      const char *btn = "left";
      if (b->mouse_button == SDL_BUTTON_RIGHT)
        btn = "right";
      else if (b->mouse_button == SDL_BUTTON_MIDDLE)
        btn = "middle";
      fprintf(f, "MOUSE %s %.3f %.3f\n", btn, b->x_pct, b->y_pct);
      break;
    }
    case KM_TYPE_AIM:
      fprintf(f, "AIM %s %.3f %.3f\n", lname, b->x_pct, b->y_pct);
      break;
    case KM_TYPE_DPAD:
      fprintf(f, "DPAD %s %.3f %.3f %.3f\n", lname, b->x_pct, b->y_pct,
              b->dpad_radius);
      break;
    case KM_TYPE_SCROLL:
      fprintf(f, "SCROLL %s %.3f %.3f\n", lname, b->x_pct, b->y_pct);
      break;
    case KM_TYPE_MACRO: {
      fprintf(f, "MACRO %s %.3f %.3f ", lname, b->x_pct, b->y_pct);
      for (int s = 0; s < b->macro_step_count; s++) {
        if (s > 0)
          fprintf(f, ";");
        fprintf(f, "%.3f,%.3f,%d", b->macro_steps[s].x_pct,
                b->macro_steps[s].y_pct, b->macro_steps[s].delay_ms);
      }
      fprintf(f, "\n");
      break;
    }
    }
  }
  fclose(f);
  LOGI("Keymapper: config saved (%d bindings)", state.count);
}

void km_reload_config(void) {
  state.loaded = false;
  km_init();
}

// =====================================================
// Lookup
// =====================================================
struct km_binding *km_find_key(SDL_Keycode kc) {
  for (int i = 0; i < state.count; i++) {
    if (state.bindings[i].type == KM_TYPE_KEY &&
        state.bindings[i].keycode == kc)
      return &state.bindings[i];
  }
  return NULL;
}

struct km_binding *km_find_mouse_binding(uint8_t button) {
  for (int i = 0; i < state.count; i++) {
    if (state.bindings[i].type == KM_TYPE_MOUSE &&
        state.bindings[i].mouse_button == button)
      return &state.bindings[i];
  }
  return NULL;
}

// =====================================================
// Toggle functions
// =====================================================
void km_toggle_edit(void) {
  state.edit_mode = !state.edit_mode;
  if (!state.edit_mode) {
    km_save_config();
    state.dragging = -1;
    state.selected = -1;
    LOGI("Keymapper: edit OFF, config saved. Restart to apply new positions.");
  } else {
    state.show_overlay = true;
    LOGI("Keymapper: edit ON - drag buttons, DELETE=remove, INS=add");
  }
}

void km_toggle_overlay(void) { state.show_overlay = !state.show_overlay; }

void km_toggle_fps(void) {
  state.fps_mode = !state.fps_mode;
  if (state.fps_mode) {
    LOGI("Keymapper: FPS Mode Enabled");
    SDL_SetRelativeMouseMode(SDL_TRUE);
  } else {
    LOGI("Keymapper: FPS Mode Disabled");
    SDL_SetRelativeMouseMode(SDL_FALSE);
  }
}

void km_adjust_opacity(float delta) {
  state.opacity += delta;
  if (state.opacity < 0.1f)
    state.opacity = 0.1f;
  if (state.opacity > 1.0f)
    state.opacity = 1.0f;
}

struct km_state *km_get_state(void) { return &state; }

// =====================================================
// Overlay Rendering (Optimized — rects instead of per-pixel circles)
// =====================================================
void km_render_overlay(SDL_Renderer *renderer, const SDL_Rect *cr,
                       struct sc_size frame_size) {
  (void)frame_size;

  if (!state.show_overlay)
    return;

  SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
  uint8_t alpha = (uint8_t)(state.opacity * 255);

  for (int i = 0; i < state.count; i++) {
    struct km_binding *b = &state.bindings[i];

    int cx = cr->x + (int)(cr->w * b->x_pct);
    int cy = cr->y + (int)(cr->h * b->y_pct);

    bool is_sel = (i == state.selected);
    bool is_mouse = (b->type == KM_TYPE_MOUSE);
    bool is_edit = state.edit_mode;

    // Button size
    int bw = 44, bh = 28;

    // Get label early to size button
    const char *label;
    char shortlabel[8];
    if (b->type == KM_TYPE_KEY || b->type == KM_TYPE_AIM ||
        b->type == KM_TYPE_DPAD || b->type == KM_TYPE_SCROLL ||
        b->type == KM_TYPE_MACRO) {
      label = SDL_GetKeyName(b->keycode);
    } else {
      if (b->mouse_button == SDL_BUTTON_LEFT)
        label = "ML";
      else if (b->mouse_button == SDL_BUTTON_RIGHT)
        label = "MR";
      else
        label = "MM";
    }
    strncpy(shortlabel, label, 6);
    shortlabel[6] = '\0';
    for (int j = 0; shortlabel[j]; j++) {
      if (shortlabel[j] >= 'a' && shortlabel[j] <= 'z')
        shortlabel[j] -= 32;
    }

    int tw = km_text_width(shortlabel, 2);
    if (tw + 12 > bw)
      bw = tw + 12;

    SDL_Rect btn = {cx - bw / 2, cy - bh / 2, bw, bh};

    // Fill color
    if (is_edit) {
      if (is_sel)
        SDL_SetRenderDrawColor(renderer, 88, 166, 255, alpha);
      else if (is_mouse)
        SDL_SetRenderDrawColor(renderer, 137, 87, 229, alpha);
      else
        SDL_SetRenderDrawColor(renderer, 40, 120, 70, alpha);
    } else {
      if (b->type == KM_TYPE_AIM)
        SDL_SetRenderDrawColor(renderer, 200, 60, 60, (uint8_t)(alpha * 0.6f));
      else if (b->type == KM_TYPE_DPAD)
        SDL_SetRenderDrawColor(renderer, 60, 60, 200, (uint8_t)(alpha * 0.6f));
      else if (b->type == KM_TYPE_SCROLL)
        SDL_SetRenderDrawColor(renderer, 200, 150, 30, (uint8_t)(alpha * 0.6f));
      else if (b->type == KM_TYPE_MACRO)
        SDL_SetRenderDrawColor(renderer, 180, 60, 180, (uint8_t)(alpha * 0.6f));
      else if (is_mouse)
        SDL_SetRenderDrawColor(renderer, 100, 40, 170, (uint8_t)(alpha * 0.5f));
      else
        SDL_SetRenderDrawColor(renderer, 0, 140, 180, (uint8_t)(alpha * 0.5f));
    }
    SDL_RenderFillRect(renderer, &btn);

    // Border (1 call instead of per-pixel circle)
    if (is_edit && is_sel)
      SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    else if (is_mouse)
      SDL_SetRenderDrawColor(renderer, 180, 120, 255, alpha);
    else
      SDL_SetRenderDrawColor(renderer, 0, 220, 240, alpha);
    SDL_RenderDrawRect(renderer, &btn);

    // Label — centered
    int tx = cx - tw / 2;
    int ty = cy - 6;
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    km_draw_text(renderer, tx, ty, shortlabel, 2);
  }
}

// =====================================================
// Edit mode mouse handling
// =====================================================
bool km_handle_edit_mouse(const SDL_Event *event, const SDL_Rect *cr,
                          struct sc_size frame_size) {
  (void)frame_size;
  if (!state.edit_mode)
    return false;

  // Hitbox radius: increased from 28 to 45 for better touch/click reliability
  const int HITBOX_SQ = 45 * 45;

  if (event->type == SDL_MOUSEBUTTONDOWN &&
      event->button.button == SDL_BUTTON_LEFT) {
    int mx = event->button.x;
    int my = event->button.y;

    for (int i = 0; i < state.count; i++) {
      struct km_binding *b = &state.bindings[i];
      int cx = cr->x + (int)(cr->w * b->x_pct);
      int cy = cr->y + (int)(cr->h * b->y_pct);
      int dx = mx - cx, dy = my - cy;
      if (dx * dx + dy * dy < HITBOX_SQ) {
        state.dragging = i;
        state.selected = i;
        return true;
      }
    }
    state.selected = -1;
    return true; // consume click
  }

  if (event->type == SDL_MOUSEMOTION && state.dragging >= 0) {
    int mx = event->motion.x;
    int my = event->motion.y;
    struct km_binding *b = &state.bindings[state.dragging];
    b->x_pct = (float)(mx - cr->x) / cr->w;
    b->y_pct = (float)(my - cr->y) / cr->h;
    if (b->x_pct < 0.0f)
      b->x_pct = 0.0f;
    if (b->x_pct > 1.0f)
      b->x_pct = 1.0f;
    if (b->y_pct < 0.0f)
      b->y_pct = 0.0f;
    if (b->y_pct > 1.0f)
      b->y_pct = 1.0f;
    return true;
  }

  if (event->type == SDL_MOUSEBUTTONUP &&
      event->button.button == SDL_BUTTON_LEFT) {
    if (state.dragging >= 0) {
      state.dragging = -1;
      return true;
    }
  }

  // Right click = Remove
  if (event->type == SDL_MOUSEBUTTONDOWN &&
      event->button.button == SDL_BUTTON_RIGHT) {
    int mx = event->button.x;
    int my = event->button.y;
    for (int i = 0; i < state.count; i++) {
      struct km_binding *b = &state.bindings[i];
      int cx = cr->x + (int)(cr->w * b->x_pct);
      int cy = cr->y + (int)(cr->h * b->y_pct);
      int dx = mx - cx, dy = my - cy;
      if (dx * dx + dy * dy < HITBOX_SQ) {
        for (int j = i; j < state.count - 1; j++) {
          state.bindings[j] = state.bindings[j + 1];
        }
        state.count--;
        state.selected = -1;
        LOGI("Keymapper: removed binding %d", i);
        return true;
      }
    }
    return true;
  }

  // Middle Click = Add basic key (Empty placeholder)
  if (event->type == SDL_MOUSEBUTTONDOWN &&
      event->button.button == SDL_BUTTON_MIDDLE) {
    if (state.count < KM_MAX_BINDINGS) {
      int mx = event->button.x;
      int my = event->button.y;
      float nx = (float)(mx - cr->x) / cr->w;
      float ny = (float)(my - cr->y) / cr->h;
      if (nx >= 0 && nx <= 1 && ny >= 0 && ny <= 1) {
        struct km_binding *b = &state.bindings[state.count];
        b->type = KM_TYPE_KEY;
        b->keycode = SDLK_UNKNOWN;
        b->x_pct = nx;
        b->y_pct = ny;
        b->pointer_id = SC_POINTER_ID_GENERIC_FINGER + 100 + state.count;
        state.selected = state.count;
        state.count++;
        LOGI("Keymapper: added blank binding at %f, %f", nx, ny);
      }
    }
    return true;
  }

  return false;
}

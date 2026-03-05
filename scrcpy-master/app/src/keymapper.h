#ifndef SC_KEYMAPPER_H
#define SC_KEYMAPPER_H

#include "common.h"
#include "control_msg.h"
#include "coords.h"
#include <SDL2/SDL.h>
#include <stdbool.h>
#include <stdint.h>

#define KM_MAX_BINDINGS 128
#define KM_MAX_MACRO_STEPS 16

#define KM_TYPE_KEY 0
#define KM_TYPE_MOUSE 1
#define KM_TYPE_AIM 2    // FPS aim anchor point
#define KM_TYPE_DPAD 3   // Virtual joystick (WASD)
#define KM_TYPE_SCROLL 4 // Mouse wheel to swipe
#define KM_TYPE_MACRO 5  // Multi-tap sequence

// Pointer ID for FPS aim finger
#define SC_POINTER_ID_AIM_FINGER (SC_POINTER_ID_GENERIC_FINGER + 200)

struct km_macro_step {
  float x_pct;
  float y_pct;
  int delay_ms; // delay before this tap
};

struct km_binding {
  int type;
  SDL_Keycode keycode;
  uint8_t mouse_button;
  float x_pct; // 0.0 - 1.0
  float y_pct;
  int pointer_id;
  // DPAD fields
  float dpad_radius; // radius as fraction of screen (e.g. 0.08)
  // MACRO fields
  struct km_macro_step macro_steps[KM_MAX_MACRO_STEPS];
  int macro_step_count;
};

struct km_state {
  struct km_binding bindings[KM_MAX_BINDINGS];
  int count;
  bool loaded;
  bool edit_mode;
  bool show_overlay;
  bool fps_mode;
  bool aim_finger_down; // whether the aim touch is currently pressed
  float opacity;        // 0.0 - 1.0
  int dragging;         // index of binding being dragged, -1 = none
  int selected;         // index of selected binding, -1 = none
};

// Initialize and load keymap.cfg
void km_init(void);

// Render overlay on top of the game
void km_render_overlay(SDL_Renderer *renderer, const SDL_Rect *content_rect,
                       struct sc_size frame_size);

// Find bindings
struct km_binding *km_find_key(SDL_Keycode kc);
struct km_binding *km_find_mouse_binding(uint8_t button);
struct km_binding *km_find_aim(void);

// Toggle edit mode (F12)
void km_toggle_edit(void);

// Toggle overlay visibility (F11)
void km_toggle_overlay(void);

// Toggle FPS lock (F10)
void km_toggle_fps(void);

// Adjust opacity with PgUp/PgDn
void km_adjust_opacity(float delta);

// Handle mouse event in edit mode
bool km_handle_edit_mouse(const SDL_Event *event, const SDL_Rect *content_rect,
                          struct sc_size frame_size);

// Save/reload config
void km_save_config(void);
void km_reload_config(void);

// Get state
struct km_state *km_get_state(void);

#endif

"""
core/port_consent.py — the one-time notice that unlocks the cross-game port tools.

What it is for
--------------
The port tools make it cheap to move an asset from one game to another, and that
is as true of someone else's released mod as it is of your own work.  The notice
does not try to police that -- it says what the tools are for, points at the one
thing a user can actually go and check (the source author's stated permissions),
and is confirmed once, ever.

Persistence
-----------
A plain file in Blender's user config dir, exactly like ``core/i18n.py``'s
language preference, rather than an ``AddonPreferences`` flag.  Both of the
alternatives reset the confirmation in normal use:

- ``AddonPreferences`` are keyed by module name, and this addon installs under
  two of them (``Modding-Toolkit`` in 4.3, ``Modding-Toolkit-dev`` in 5.1), so a
  rename or a re-install silently loses the flag.
- Anything stored inside the addon directory is at the mercy of the updater,
  which merges over that directory on every release.

The config dir survives updates, re-installs and version bumps, which is what
the button promises when it only asks once.  Blender 4.3 and 5.1 keep separate
config dirs, so those two installs are confirmed separately -- correct, since
they are two installs.

Gating
------
Two layers, because hiding the buttons is not the same as disabling the tools:

- ``draw_gate()`` replaces the whole 移植 group with the notice button.
- ``gate()`` wraps each port operator's ``poll``, so reaching one through the
  search menu, a keymap or a script hits the same gate.
"""

import os

import bpy

from .i18n import T


#: Cached tri-state: None = not read from disk yet, else bool.
_GRANTED = None


def _config_path() -> str:
    """Consent marker path (user config dir, outside the addon and its updater)."""
    try:
        cfg = bpy.utils.user_resource("CONFIG")
    except Exception:
        cfg = os.path.expanduser("~")
    return os.path.join(cfg, "modding_toolkit_port_consent.txt")


def load_consent() -> bool:
    """Read the marker back from disk (called from register(), and lazily below)."""
    global _GRANTED
    try:
        _GRANTED = os.path.isfile(_config_path())
    except Exception:
        _GRANTED = False
    return _GRANTED


def has_consent() -> bool:
    """True once the notice has been confirmed on this machine."""
    if _GRANTED is None:
        return load_consent()
    return _GRANTED


def grant() -> None:
    """Record the confirmation.  A failed write is not fatal -- the session stays
    unlocked and the notice simply comes back next time, which is the safe way
    round for a read-only or unwritable config dir."""
    global _GRANTED
    _GRANTED = True
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            f.write("1\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# The notice itself
# ─────────────────────────────────────────────────────────────────────────────

#: The three paragraphs, in order.  Line breaks inside each are hard-coded in the
#: string table rather than wrapped here: Blender's UILayout does not wrap, and
#: textwrap splits on spaces, which does nothing useful for the 中文 version.
_BODY_KEYS = ("core.port_consent.body_1",
              "core.port_consent.body_2",
              "core.port_consent.body_3")


def _draw_notice(layout):
    col = layout.column(align=True)
    for i, key in enumerate(_BODY_KEYS):
        if i:
            col.separator()
        for line in T(key).split("\n"):
            col.label(text=line)


class MT_OT_PortConsent(bpy.types.Operator):
    """Show the cross-game porting notice and record that it was read"""

    bl_idname = "mt.port_consent"
    bl_label = "Cross-Game Porting"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, properties):
        return T("core.port_consent.btn_unlock_desc")

    def invoke(self, context, event):
        wm = context.window_manager
        # title=/confirm_text= are 4.x additions; fall back rather than fail on
        # an older build, where the dialog still shows the same body text.
        try:
            return wm.invoke_props_dialog(
                self, width=460,
                title=T("core.port_consent.title"),
                confirm_text=T("core.port_consent.confirm"))
        except TypeError:
            return wm.invoke_props_dialog(self, width=460)

    def draw(self, context):
        _draw_notice(self.layout)

    def execute(self, context):
        grant()
        try:
            for win in context.window_manager.windows:
                for area in win.screen.areas:
                    area.tag_redraw()
        except Exception:
            pass
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Gates
# ─────────────────────────────────────────────────────────────────────────────

def draw_gate(layout) -> bool:
    """Draw the locked state of the 移植 group.  True = already confirmed, the
    caller should draw its real contents."""
    if has_consent():
        return True
    col = layout.column(align=True)
    col.operator("mt.port_consent",
                 text=T("core.port_consent.btn_unlock"), icon='INFO')
    col.label(text=T("core.port_consent.gate_hint"))
    return False


def gate(cls):
    """Class decorator: refuse to run a port operator until the notice is
    confirmed, keeping whatever ``poll`` the class already defines."""
    original = cls.__dict__.get('poll')

    @classmethod
    def poll(c, context):
        if not has_consent():
            try:
                c.poll_message_set(T("core.port_consent.poll_blocked"))
            except Exception:
                pass
            return False
        if original is None:
            return True
        return original.__func__(c, context)

    cls.poll = poll
    return cls


# ─────────────────────────────────────────────────────────────────────────────
# register / unregister
# ─────────────────────────────────────────────────────────────────────────────

classes = [MT_OT_PortConsent]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    load_consent()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

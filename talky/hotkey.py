from __future__ import annotations

import threading
from collections.abc import Callable


def label_for_hotkey_tokens(tokens: list[str]) -> str:
    labels = {
        "alt": "Option",
        "alt_l": "Left Option",
        "alt_r": "Right Option",
        "cmd": "Command",
        "cmd_l": "Left Command",
        "cmd_r": "Right Command",
        "ctrl": "Control",
        "ctrl_l": "Left Control",
        "ctrl_r": "Right Control",
        "shift": "Shift",
        "shift_l": "Left Shift",
        "shift_r": "Right Shift",
        "fn": "Fn",
        "space": "Space",
        "enter": "Enter",
        "esc": "Esc",
    }
    pretty: list[str] = []
    for token in tokens:
        if token.startswith("f") and token[1:].isdigit():
            pretty.append(token.upper())
        else:
            pretty.append(labels.get(token, token))
    return " + ".join(pretty)


class HoldToTalkHotkey:
    """
    Press-and-hold hotkey handler.

    On macOS, standalone Fn/Globe listening can be unreliable in high-level hooks.
    We first try Quartz flagsChanged with SecondaryFn mask; if unavailable, we
    gracefully fall back to Right Option (`alt_r`).
    """

    def __init__(
        self,
        key_mode: str,
        custom_keys: list[str],
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self.key_mode = key_mode
        self.custom_keys = [k.strip().lower() for k in custom_keys if k.strip()]
        self.on_press = on_press
        self.on_release = on_release
        self._pressed = False
        self._quartz_thread: threading.Thread | None = None
        self._run_loop = None
        self._using_fallback = False

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    def start(self) -> None:
        if self.key_mode == "fn":
            started = self._start_fn_quartz_listener()
            if started:
                return
            self._using_fallback = True
            self._start_modifier_quartz_listener(required={"alt"})
            return

        if self.key_mode == "right_option":
            self._start_modifier_quartz_listener(required={"alt"})
            return
        if self.key_mode == "right_command":
            self._start_modifier_quartz_listener(required={"cmd"})
            return
        if self.key_mode == "command_option":
            self._start_modifier_quartz_listener(required={"cmd", "alt"})
            return
        if self.key_mode == "custom":
            supported = {"alt", "cmd", "ctrl", "shift", "fn"}
            required = {k for k in self.custom_keys if k in supported}
            if not required:
                required = {"alt"}
            self._start_modifier_quartz_listener(required=required)
            return

        self._start_modifier_quartz_listener(required={"alt"})

    def stop(self) -> None:
        if self._run_loop is not None:
            try:
                import Quartz

                Quartz.CFRunLoopStop(self._run_loop)
            except Exception:
                pass
            self._run_loop = None
        self._quartz_thread = None
        self._pressed = False

    def _start_modifier_quartz_listener(self, required: set[str]) -> None:
        try:
            import Quartz
        except Exception:
            return

        alt_mask = getattr(Quartz, "kCGEventFlagMaskAlternate", 0)
        cmd_mask = getattr(Quartz, "kCGEventFlagMaskCommand", 0)
        ctrl_mask = getattr(Quartz, "kCGEventFlagMaskControl", 0)
        shift_mask = getattr(Quartz, "kCGEventFlagMaskShift", 0)
        fn_mask = getattr(Quartz, "kCGEventFlagMaskSecondaryFn", 0)

        def _run_event_tap() -> None:
            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event

                flags = Quartz.CGEventGetFlags(event)
                current: set[str] = set()
                if flags & alt_mask:
                    current.add("alt")
                if flags & cmd_mask:
                    current.add("cmd")
                if flags & ctrl_mask:
                    current.add("ctrl")
                if flags & shift_mask:
                    current.add("shift")
                if fn_mask and (flags & fn_mask):
                    current.add("fn")

                is_match = required.issubset(current)
                if is_match and not self._pressed:
                    self._pressed = True
                    self.on_press()
                elif not is_match and self._pressed:
                    self._pressed = False
                    self.on_release()
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                _callback,
                None,
            )
            if tap is None:
                return

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = Quartz.CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            Quartz.CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()

    def _start_fn_quartz_listener(self) -> bool:
        try:
            import Quartz
        except Exception:
            return False

        fn_mask = getattr(Quartz, "kCGEventFlagMaskSecondaryFn", None)
        if fn_mask is None:
            return False

        def _run_event_tap() -> None:
            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event
                flags = Quartz.CGEventGetFlags(event)
                is_pressed = bool(flags & fn_mask)
                if is_pressed and not self._pressed:
                    self._pressed = True
                    self.on_press()
                elif not is_pressed and self._pressed:
                    self._pressed = False
                    self.on_release()
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                _callback,
                None,
            )
            if tap is None:
                self._using_fallback = True
                self._start_modifier_quartz_listener(required={"alt"})
                return

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = Quartz.CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            Quartz.CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()
        return True


class GlobalShortcutListener:
    """
    Global shortcut listener for Command+Option+Control.
    Uses Quartz flagsChanged event tap to avoid pynput/ctypes instability
    seen on some macOS input-method environments.
    """

    def __init__(self, on_trigger: Callable[[], None]) -> None:
        self.on_trigger = on_trigger
        self._quartz_thread: threading.Thread | None = None
        self._run_loop = None
        self._triggered_while_held = False

    def start(self) -> None:
        if self._quartz_thread is not None:
            return
        try:
            import Quartz
        except Exception:
            return

        alt_mask = getattr(Quartz, "kCGEventFlagMaskAlternate", 0)
        cmd_mask = getattr(Quartz, "kCGEventFlagMaskCommand", 0)
        ctrl_mask = getattr(Quartz, "kCGEventFlagMaskControl", 0)

        def _run_event_tap() -> None:
            def _callback(proxy, event_type, event, refcon):
                del proxy, refcon
                if event_type != Quartz.kCGEventFlagsChanged:
                    return event
                flags = Quartz.CGEventGetFlags(event)
                match = bool((flags & alt_mask) and (flags & cmd_mask) and (flags & ctrl_mask))
                if match and not self._triggered_while_held:
                    self._triggered_while_held = True
                    self.on_trigger()
                elif not match:
                    self._triggered_while_held = False
                return event

            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                _callback,
                None,
            )
            if tap is None:
                return
            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = Quartz.CFRunLoopGetCurrent()
            self._run_loop = run_loop
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            Quartz.CFRunLoopRun()

        self._quartz_thread = threading.Thread(target=_run_event_tap, daemon=True)
        self._quartz_thread.start()

    def stop(self) -> None:
        if self._run_loop is not None:
            try:
                import Quartz

                Quartz.CFRunLoopStop(self._run_loop)
            except Exception:
                pass
            self._run_loop = None
        self._quartz_thread = None
        self._triggered_while_held = False

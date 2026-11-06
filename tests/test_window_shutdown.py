import ast
import asyncio
import copy
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parents[1]
tree = ast.parse((HERE/'Anki-TTS-Flet'/'main.py').read_text(encoding='utf-8'))
main = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'main')
defs = {n.name:n for n in main.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
factory = ast.parse('''
def make_callbacks():
    shutdown_started = False
    def on_tray_exit():
        pending.append(asyncio.create_task(destroy_main_window()))
    return destroy_main_window, window_event, lambda: shutdown_started
''')
outer = factory.body[0]
outer.body[1:1] = [copy.deepcopy(defs[n]) for n in ('maybe_await','destroy_main_window','window_event')]
ast.fix_missing_locations(factory)

class WindowShutdownTests(unittest.IsolatedAsyncioTestCase):
    def setup_scenario(self, platform='nt', tray=False, gate=None):
        calls = []
        page = SimpleNamespace()
        window = SimpleNamespace(prevent_close=True, visible=True)
        page.window = window
        page.update = lambda: calls.append('update')
        pending = []
        def close():
            calls.append(('close', window.prevent_close))
            event(SimpleNamespace(data='close'))
        window.close = close
        window.destroy = lambda: calls.append('destroy')
        async def cancel_active(reason):
            calls.append(('cancel',reason))
            if gate:
                await gate.wait()
        env = {
            'asyncio':asyncio,'inspect':inspect,'page':page,'pending':pending,
            'os':SimpleNamespace(name=platform),
            'monitor_manager':SimpleNamespace(stop_monitors=lambda:calls.append('monitor.stop')),
            'tray_manager':SimpleNamespace(stop=lambda:calls.append('tray.stop')),
            'tts_manager':SimpleNamespace(get_provider=lambda _:SimpleNamespace(cancel_active=cancel_active)),
            'settings_manager':SimpleNamespace(get=lambda key,default=None:tray),
            'print':lambda *args:None,
        }
        exec(compile(factory,'candidate_callbacks','exec'),env)
        destroy,event,state=env['make_callbacks']()
        return destroy,event,state,calls,pending,env

    async def test_windows_cleanup_precedes_normal_close_and_native_event_does_not_reenter(self):
        destroy,event,state,calls,pending,env = self.setup_scenario()
        await destroy()
        self.assertEqual(calls,['monitor.stop','tray.stop',('cancel','shutdown'),('close',False)])
        self.assertEqual(pending,[])
        self.assertTrue(state())
        await destroy()
        self.assertEqual(len(calls),4)

    async def test_close_to_tray_remains_hide_without_cleanup(self):
        destroy,event,state,calls,pending,env = self.setup_scenario(tray=True)
        event(SimpleNamespace(data='close'))
        self.assertFalse(env['page'].window.visible)
        self.assertEqual(calls,['update'])
        self.assertTrue(env['page'].window.prevent_close)
        self.assertFalse(state())
        self.assertEqual(pending,[])

    async def test_concurrent_shutdown_during_cancel_runs_cleanup_once(self):
        gate=asyncio.Event()
        destroy,event,state,calls,pending,env=self.setup_scenario(gate=gate)
        first=asyncio.create_task(destroy())
        await asyncio.sleep(0)
        await asyncio.wait_for(destroy(), timeout=1)
        event(SimpleNamespace(data='close'))
        self.assertEqual(pending,[])
        gate.set()
        await first
        self.assertEqual(calls,['monitor.stop','tray.stop',('cancel','shutdown'),('close',False)])

    async def test_cleanup_failure_rethrows_and_allows_retry(self):
        destroy,event,state,calls,pending,env=self.setup_scenario()
        def fail(): raise RuntimeError('stop failed')
        env['monitor_manager'].stop_monitors=fail
        with self.assertRaisesRegex(RuntimeError,'stop failed'):
            await destroy()
        self.assertFalse(state())
        self.assertTrue(env['page'].window.prevent_close)
        env['monitor_manager'].stop_monitors=lambda:calls.append('monitor.stop')
        await destroy()
        self.assertEqual(calls[-1],('close',False))

    async def test_cancelled_cleanup_resets_guard(self):
        gate=asyncio.Event()
        destroy,event,state,calls,pending,env=self.setup_scenario(gate=gate)
        task=asyncio.create_task(destroy())
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertFalse(state())

    async def test_non_windows_keeps_destroy_path(self):
        destroy,event,state,calls,pending,env=self.setup_scenario(platform='posix')
        await destroy()
        self.assertEqual(calls[-1],'destroy')
        self.assertTrue(env['page'].window.prevent_close)

if __name__=='__main__': unittest.main(verbosity=2)

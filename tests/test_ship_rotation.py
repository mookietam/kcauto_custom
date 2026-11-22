"""Offline regression tests. Run from the checkout: python -m unittest discover -s tests."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kcauto"))
from args.args_core import args
from cui.store import ConfigStore
from util.logger import Log

TEMPLATE = ROOT / "template/configs/config_cui.json"
# The upstream core constructs singletons at import time, including its game
# client. Use the normal import order but do not connect to a browser.
with patch.object(sys, "argv", ["kcauto", "--cfg-path", str(TEMPLATE)]), \
        patch.dict(sys.modules, {"util.kca": MagicMock()}), patch.object(Log, "enabled", False):
    args.parse_args()
    import startup.kcauto as app


def rule(lock):
    return "morale:<:30|" + ":".join(["ship", "42", "", "", "", "", "", "", lock, ""])


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(Log, "enabled", False))

    def test_custom_combat_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            slots = {"2": rule("locked")}
            path.write_text(json.dumps({
                "combat.enabled": True, "ship_switcher.enabled": True,
                "ship_switcher.slots": slots,
            }))
            store = ConfigStore(path, TEMPLATE)
            self.assertFalse(store.is_dirty)
            store.set("ship_switcher.enabled", False)
            store.set("ship_switcher.enabled", True)
            store.save()
            store.load()
            self.assertTrue(store.get("ship_switcher.enabled"))
            self.assertEqual(store.get("ship_switcher.slots"), slots)

    def test_sparse_rules_docked_copy_and_lock_filters(self):
        def ship(id_, locked):
            return Obj(production_id=id_, sortno=42, sort_id=1, level=100-id_,
                       name="same model", locked=locked, morale=20)
        ships = [ship(1, True), ship(2, True), ship(3, False), ship(4, True)]
        fleet = Obj(ships=[ships[0], ships[0]])
        docks = app.rep.RepairCore()
        docks.update_repair_data([{"api_ship_id": 2, "api_state": 1, "api_complete_time": 1800000000000}])
        with patch.object(app.rep, "repair", docks), \
                patch.object(app.flt, "fleets", Obj(ships_in_fleets=[ships[0]])), \
                patch.object(app.shp.ships, "ship_pool", {s.production_id: s for s in ships}):
            for criterion, expected in [("locked", 4), ("unlocked", 3), ("", 3)]:
                with self.subTest(criterion=criterion), patch.object(
                    app.cfg.config, "ship_switcher", Obj(enabled=True, slots={2: rule(criterion)})
                ):
                    switcher = app.ssw.ShipSwitcherCore()
                    selected = switcher.get_ship_switch_list(fleet)
                    self.assertEqual([(s["slot_id"], s["ship"].production_id) for s in selected], [(2, expected)])
            docks.update_repair_data([{"api_ship_id": 0, "api_state": 0}])
            with patch.object(app.cfg.config, "ship_switcher", Obj(enabled=True, slots={2: rule("locked")})):
                switcher.update_from_config()
                self.assertEqual(switcher.get_ship_switch_list(fleet)[0]["ship"].production_id, 2)

    def test_combat_rotates_after_preset_before_repairs(self):
        map_ = app.MapEnum.W1_1
        combat = MagicMock(enabled=True, time_to_sortie=True)
        combat.get_sortie_queue.return_value = [map_]
        combat.should_and_able_to_sortie.return_value = False
        combat_config = Obj(sortie_map=map_, override=True)
        fleet = Obj(ships=[])
        events = []
        bot = object.__new__(app.Kcauto)
        bot._run_fleetswitch_logic = lambda context: events.append(context) or 0
        bot.run_shipswitch_logic = lambda **kw: events.append(kw["fleet"]) or True
        bot.run_repair_logic = lambda **kw: events.append("repair")
        with patch.object(app.cfg, "config", Obj(combat=combat_config, ship_switcher=Obj(enabled=True))), \
                patch.object(app.com, "combat", combat), patch.object(app.nav, "navigate", MagicMock()), \
                patch.object(app.flt, "fleets", Obj(combat_fleets=[fleet])):
            bot.run_combat_logic()
        self.assertEqual(events, ["combat", fleet, "repair"])


if __name__ == "__main__":
    unittest.main()

"""Native map behavior checks independent of the main-window layout."""

import copy
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from dayframe.ui.views.project_map import ARROW_LENGTH, ProjectMap, SectionHeader, CONTENT_X, CONTENT_Y

APP = QApplication.instance() or QApplication([])


def ticket(record_id, **fields):
    return {
        "id": record_id,
        "project_id": "p",
        "title": "Ticket " + record_id,
        "description": "",
        "status": "ready",
        "priority": "medium",
        "estimate_min": 30,
        "dependencies": [],
        "archived": 0,
        "component": "",
        "milestone": "",
        "labels": [],
        **fields,
    }


class MapWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.selected = None
        self.actions = []
        self.edited = []
        self.data = {
            "ticket": [ticket("a"), ticket("b"), ticket("c")],
            "section": [
                {
                    "id": "front",
                    "project_id": "p",
                    "name": "Frontend",
                    "rule_field": "component",
                    "rule_value": "UI",
                    "sort_order": 0,
                },
                {
                    "id": "release",
                    "project_id": "p",
                    "name": "Release",
                    "rule_field": "milestone",
                    "rule_value": "R1",
                    "sort_order": 1,
                },
            ],
            "placement": [
                {"id": "a", "ticket_id": "a", "section_id": "front", "manual": 0, "x": 0, "y": 0},
                {"id": "b", "ticket_id": "b", "section_id": "front", "manual": 0, "x": 0, "y": 0},
                {"id": "c", "ticket_id": "c", "section_id": "", "manual": 0, "x": 0, "y": 0},
            ],
        }

    def ticket_key(self, ticket):
        return "T-" + ticket["id"]

    def blocked(self, ticket):
        return False

    def code_repo(self, project_id):
        return None

    def changeset_count(self, ticket_id):
        return 0

    def select_ticket(self, ticket_id, rebuild=False):
        self.selected = ticket_id

    def execute(self, method, payload, refresh=True):
        self.actions.append((method, payload))
        return True

    def refresh(self):
        pass

    def edit_section(self, section):
        self.edited.append(section["id"])


class MapUiTests(unittest.TestCase):
    def setUp(self):
        self.window = MapWindow()
        self.view = None

    def tearDown(self):
        if self.view:
            self.view.close()
            self.view.deleteLater()
            self.view = None
        self.window.close()
        self.window.deleteLater()
        self.window = None
        APP.processEvents()
        # unittest keeps finished tests alive; flush deleteLater() so widgets do not pile up.
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def show_map(self):
        self.view = ProjectMap(self.window, "p")
        self.view.resize(760, 440)
        self.view.show()
        APP.processEvents()
        return self.view

    def stack_three(self):
        """a, b and c stacked in Frontend, with c depending on a across b."""
        data = self.window.data
        data["ticket"][2] = ticket("c", dependencies=["a"])
        data["placement"][2]["section_id"] = "front"
        data["section"].append(
            {
                "id": "inner",
                "project_id": "p",
                "name": "Inner",
                "rule_field": "",
                "rule_value": "",
                "sort_order": 2,
                "parent_id": "front",
            }
        )

    def test_links_route_around_unrelated_cards(self):
        self.stack_three()
        view = self.show_map()
        self.assertEqual(len(view.edge_records), 1)
        record = view.edge_records[0]
        others = [view.nodes["b"].sceneBoundingRect()]
        self.assertEqual(view.crossings(record["path"].path(), others), 0)
        self.assertEqual(len(record["items"]), 2)  # line and arrow, no portals needed
        # When nothing can avoid a card, portals mark where the line passes under it.
        blocked = view.portals(record["path"].path(), [record["path"].path().boundingRect()], "#ffffff")
        self.assertTrue(blocked)

    def test_links_meet_cards_squarely_and_share_a_side_without_overlapping(self):
        self.stack_three()
        # b becomes a child of a as well, so two links leave a.
        self.window.data["ticket"][1] = ticket("b", parent_id="a")
        view = self.show_map()
        self.assertEqual(len(view.edge_records), 2)
        cards = [node.sceneBoundingRect() for node in view.nodes.values()]
        sources = []
        for record in view.edge_records:
            line = record["path"].path()
            head = record["items"][1].path()
            # The line is drawn from inside the arrowhead back to its source card, so
            # nothing pokes past the tip, and its last stretch runs along one axis only.
            inside, sources_end = line.pointAtPercent(0), line.pointAtPercent(1)
            self.assertTrue(head.contains(inside))
            near = line.pointAtPercent(line.percentAtLength(2))
            self.assertTrue(abs(near.x() - inside.x()) < 0.05 or abs(near.y() - inside.y()) < 0.05)
            # The head is as long as designed and its tip rests on a card edge from outside.
            tips = [
                card
                for card in cards
                if not card.contains(inside)
                and abs(
                    min(
                        abs(inside.x() - card.left()),
                        abs(inside.x() - card.right()),
                        abs(inside.y() - card.top()),
                        abs(inside.y() - card.bottom()),
                    )
                    - ARROW_LENGTH * 0.6
                )
                < 0.01
            ]
            self.assertTrue(tips)
            sources.append(sources_end)
        # Both links start on a, at different points.
        self.assertGreater((sources[0] - sources[1]).manhattanLength(), 8)

    def test_hovering_a_card_focuses_its_links(self):
        self.stack_three()
        view = self.show_map()
        view.focus_links("b")
        self.assertLess(view.edge_records[0]["path"].opacity(), 0.5)
        view.focus_links("c")
        self.assertEqual(view.focus_ids, {"a", "c"})
        self.assertEqual(view.edge_records[0]["path"].opacity(), 1.0)
        self.assertTrue(view.ant_timer.isActive())
        offset = view.edge_records[0]["path"].pen().dashOffset()
        view.march()
        self.assertNotEqual(view.edge_records[0]["path"].pen().dashOffset(), offset)
        view.focus_links(None)
        self.assertFalse(view.ant_timer.isActive())

    def test_dragging_a_section_carries_nested_sections_and_cards(self):
        self.stack_three()
        view = self.show_map()
        header = view.headers["front"]
        inner = view.headers["inner"]
        before = {
            "inner": QPointF(inner.pos()),
            "region": QPointF(view.region_items["inner"].pos()),
            "a": QPointF(view.nodes["a"].pos()),
        }
        header.origin = QPointF(header.pos())
        view.begin_carry(header)
        view.carry_to(QPointF(90, 40))
        self.assertEqual(inner.pos(), before["inner"] + QPointF(90, 40))
        self.assertEqual(view.region_items["inner"].pos(), before["region"] + QPointF(90, 40))
        self.assertEqual(view.nodes["a"].pos(), before["a"] + QPointF(90, 40))
        self.assertLess(view.nodes["a"].opacity(), 1.0)
        view.end_carry()
        self.assertEqual(view.nodes["a"].pos(), before["a"])
        self.assertEqual(view.nodes["a"].opacity(), 1.0)
        self.assertEqual(inner.pos(), before["inner"])

    def test_compact_scene_and_zoom_fit(self):
        view = self.show_map()
        self.assertLess(view.sceneRect().width(), 700)
        self.assertLess(view.sceneRect().height(), 300)
        self.assertLessEqual(view.zoom_percent(), 100)
        self.assertFalse(view.grab().isNull())
        before = view.zoom_percent()
        view.zoom_by(1.15)
        self.assertGreater(view.zoom_percent(), before)
        view.fit()
        self.assertLessEqual(view.zoom_percent(), 100)
        self.assertEqual(len(view.nodes), 2)
        self.assertEqual(len(view.unsorted), 1)

    def test_saved_manual_offsets_are_not_rescaled_or_written(self):
        self.window.data["placement"][0].update(manual=1, x=20, y=47)
        original = copy.deepcopy(self.window.data["placement"])
        view = self.show_map()
        region = next(rect for section, rect in view.regions if section["id"] == "front")
        node = view.nodes["a"]
        self.assertEqual(node.pos().x() - region.x() - CONTENT_X, 20)
        self.assertEqual(node.pos().y() - region.y() - CONTENT_Y, 47)
        self.assertFalse(node.sceneBoundingRect().intersects(view.nodes["b"].sceneBoundingRect()))
        self.assertEqual(self.window.data["placement"], original)
        self.assertEqual(self.window.actions, [])

    def test_section_header_edits_and_drag_keeps_preview_undo(self):
        view = self.show_map()
        header = next(
            x for x in view.scene().items() if isinstance(x, SectionHeader) and x.section["id"] == "front"
        )
        at = view.mapFromScene(header.sceneBoundingRect().center())
        QTest.mouseDClick(view.viewport(), Qt.LeftButton, pos=at)
        QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=at)
        APP.processEvents()
        self.assertEqual(self.window.edited, ["front"])
        node = view.nodes["a"]
        start = view.mapFromScene(node.sceneBoundingRect().center())
        target = next(rect for section, rect in view.regions if section["id"] == "release")
        end = view.mapFromScene(target.center())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
            for at in (start + (end - start) / 2, end):
                move = QMouseEvent(
                    QEvent.MouseMove,
                    QPointF(at),
                    QPointF(view.viewport().mapToGlobal(at)),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                )
                APP.sendEvent(view.viewport(), move)
            QTest.qWait(1600)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=end)
            APP.processEvents()
        self.assertEqual(self.window.actions[-1][0], "placement.save")
        self.assertEqual(self.window.actions[-1][1]["section_id"], "release")
        self.window.undo_action()
        self.assertEqual(self.window.actions[-1][0], "map.restore")
        self.assertTrue(
            any(
                r["kind"] == "placement" and r["data"]["section_id"] == "front"
                for r in self.window.actions[-1][1]["records"]
            )
        )


if __name__ == "__main__":
    unittest.main()

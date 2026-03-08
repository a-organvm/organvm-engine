"""Tests for cli/study.py — Study Suite CLI commands."""

import json
import pytest
from unittest.mock import patch, MagicMock

from organvm_engine.cli.study import (
    cmd_study_feedback,
    cmd_study_consilience,
    cmd_study_audit_report,
)


class TestCmdStudyFeedback:
    def test_returns_zero(self, capsys):
        args = MagicMock()
        args.json = False
        args.polarity = None
        rc = cmd_study_feedback(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Feedback Loop Inventory" in out

    def test_json_output(self, capsys):
        args = MagicMock()
        args.json = True
        args.polarity = None
        rc = cmd_study_feedback(args)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "total" in data
        assert "loops" in data
        assert data["total"] > 0

    def test_filter_positive(self, capsys):
        args = MagicMock()
        args.json = False
        args.polarity = "positive"
        rc = cmd_study_feedback(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "POSITIVE" in out

    def test_filter_negative(self, capsys):
        args = MagicMock()
        args.json = False
        args.polarity = "negative"
        rc = cmd_study_feedback(args)
        assert rc == 0

    def test_json_with_polarity_filter(self, capsys):
        args = MagicMock()
        args.json = True
        args.polarity = "positive"
        rc = cmd_study_feedback(args)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        for loop in data["loops"]:
            assert loop["polarity"] == "positive"


class TestCmdStudyConsilience:
    @patch("organvm_engine.metrics.consilience.compute_consilience")
    def test_returns_zero(self, mock_cc, capsys):
        from organvm_engine.metrics.consilience import ConsilienceReport
        mock_cc.return_value = ConsilienceReport()
        args = MagicMock()
        args.json = False
        rc = cmd_study_consilience(args)
        assert rc == 0

    @patch("organvm_engine.metrics.consilience.compute_consilience")
    def test_json_output(self, mock_cc, capsys):
        from organvm_engine.metrics.consilience import ConsilienceReport, PrincipleRecord
        report = ConsilienceReport(
            principles=[
                PrincipleRecord(
                    code="Y1", title="Test", source_text="src",
                    sources=["a"], domains=["eng"],
                ),
            ],
        )
        mock_cc.return_value = report
        args = MagicMock()
        args.json = True
        rc = cmd_study_consilience(args)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["principle_count"] == 1


class TestCmdStudyAuditReport:
    @patch("organvm_engine.metrics.consilience.compute_consilience")
    @patch("organvm_engine.governance.audit.run_audit")
    @patch("organvm_engine.registry.loader.load_registry")
    @patch("organvm_engine.paths.registry_path")
    def test_json_output(self, mock_rp, mock_lr, mock_audit, mock_cc, capsys):
        from organvm_engine.governance.audit import AuditResult
        from organvm_engine.metrics.consilience import ConsilienceReport

        mock_rp.return_value = "/tmp/test"
        mock_lr.return_value = {"organs": {}}
        mock_audit.return_value = AuditResult()
        mock_cc.return_value = ConsilienceReport()

        args = MagicMock()
        args.json = True
        args.output = None
        rc = cmd_study_audit_report(args)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "governance" in data
        assert "feedback_loops" in data
        assert "consilience" in data

    @patch("organvm_engine.metrics.consilience.compute_consilience")
    @patch("organvm_engine.governance.audit.run_audit")
    @patch("organvm_engine.registry.loader.load_registry")
    @patch("organvm_engine.paths.registry_path")
    def test_text_output(self, mock_rp, mock_lr, mock_audit, mock_cc, capsys):
        from organvm_engine.governance.audit import AuditResult
        from organvm_engine.metrics.consilience import ConsilienceReport

        mock_rp.return_value = "/tmp/test"
        mock_lr.return_value = {"organs": {}}
        mock_audit.return_value = AuditResult()
        mock_cc.return_value = ConsilienceReport()

        args = MagicMock()
        args.json = False
        args.output = None
        rc = cmd_study_audit_report(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Study Suite" in out
        assert "Governance Audit Report" in out

    @patch("organvm_engine.metrics.consilience.compute_consilience")
    @patch("organvm_engine.governance.audit.run_audit")
    @patch("organvm_engine.registry.loader.load_registry")
    @patch("organvm_engine.paths.registry_path")
    def test_write_to_file(self, mock_rp, mock_lr, mock_audit, mock_cc, tmp_path, capsys):
        from organvm_engine.governance.audit import AuditResult
        from organvm_engine.metrics.consilience import ConsilienceReport

        mock_rp.return_value = "/tmp/test"
        mock_lr.return_value = {"organs": {}}
        mock_audit.return_value = AuditResult()
        mock_cc.return_value = ConsilienceReport()

        output_file = tmp_path / "report.md"
        args = MagicMock()
        args.json = False
        args.output = str(output_file)
        rc = cmd_study_audit_report(args)
        assert rc == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "Study Suite" in content

    @patch("organvm_engine.metrics.consilience.compute_consilience")
    @patch("organvm_engine.governance.audit.run_audit")
    @patch("organvm_engine.registry.loader.load_registry")
    @patch("organvm_engine.paths.registry_path")
    def test_returns_nonzero_on_critical(self, mock_rp, mock_lr, mock_audit, mock_cc, capsys):
        from organvm_engine.governance.audit import AuditResult
        from organvm_engine.metrics.consilience import ConsilienceReport

        mock_rp.return_value = "/tmp/test"
        mock_lr.return_value = {"organs": {}}
        audit = AuditResult(critical=["Something critical"])
        mock_audit.return_value = audit
        mock_cc.return_value = ConsilienceReport()

        args = MagicMock()
        args.json = False
        args.output = None
        rc = cmd_study_audit_report(args)
        assert rc == 1

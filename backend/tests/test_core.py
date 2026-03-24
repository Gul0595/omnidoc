"""
Tests for LLM chain, sectors, and intent classification.
Run: pytest tests/ -v
No API keys needed — all providers mocked.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSectors:
    def test_all_six_present(self):
        from sectors import ALL_SECTORS
        assert set(ALL_SECTORS.keys()) == {
            "agriculture", "healthcare", "education", "military", "household", "it"}

    def test_every_sector_has_required_fields(self):
        from sectors import ALL_SECTORS
        for sid, s in ALL_SECTORS.items():
            assert s.id == sid
            assert len(s.persona) > 50,      f"{sid}: persona too short"
            assert len(s.patterns) >= 4,     f"{sid}: needs ≥4 patterns"
            assert len(s.suggestions) >= 4,  f"{sid}: needs ≥4 suggestions"
            assert "workspace"  in s.terminology
            assert "document"   in s.terminology
            assert "query"      in s.terminology
            assert "user_label" in s.terminology

    def test_fallback_to_it(self):
        from sectors import get_sector
        assert get_sector("nonexistent").id == "it"

    def test_agriculture_msp_pattern(self):
        import re
        from sectors import get_sector
        s = get_sector("agriculture")
        assert any(re.search(p, "MSP: Rs. 2275 per quintal", re.I)
                   for p, _ in s.patterns)

    def test_healthcare_dosage_pattern(self):
        import re
        from sectors import get_sector
        s = get_sector("healthcare")
        assert any(re.search(p, "Amoxicillin 500mg twice daily", re.I)
                   for p, _ in s.patterns)

    def test_it_cve_pattern(self):
        import re
        from sectors import get_sector
        s = get_sector("it")
        assert any(re.search(p, "Affected by CVE-2024-1234", re.I)
                   for p, _ in s.patterns)


class TestLLMChain:
    def test_builds_with_groq(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("OLLAMA_URL",            raising=False)
        monkeypatch.delenv("GEMINI_API_KEY",        raising=False)
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY",   raising=False)
        import importlib, core.llm_chain as m
        importlib.reload(m)
        chain = m.LLMChain()
        assert chain.chain[0].value == "groq"

    def test_raises_with_no_providers(self, monkeypatch):
        for k in ["OLLAMA_URL", "GROQ_API_KEY", "GEMINI_API_KEY",
                  "CLOUDFLARE_ACCOUNT_ID", "HUGGINGFACE_API_KEY"]:
            monkeypatch.delenv(k, raising=False)
        import importlib, core.llm_chain as m
        importlib.reload(m)
        try:
            m.LLMChain()
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "No LLM provider" in str(e)

    def test_ollama_is_first_when_set(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_URL",    "http://localhost:11434")
        monkeypatch.setenv("GROQ_API_KEY",  "test-key")
        import importlib, core.llm_chain as m
        importlib.reload(m)
        chain = m.LLMChain()
        assert chain.chain[0].value == "ollama"

    def test_status_structure(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        import importlib, core.llm_chain as m
        importlib.reload(m)
        status = m.LLMChain().status()
        assert "chain" in status
        assert "primary" in status
        assert "fallbacks" in status


class TestIntentClassification:
    def _engine(self):
        from core.rag_engine import RAGEngine
        e = RAGEngine.__new__(RAGEngine)
        e.workspace_id = "test"; e.sector_id = "it"
        from sectors import get_sector; e.sector = get_sector("it")
        return e

    def test_extractive_how_much(self):
        assert self._engine().is_extractive("How much does the service cost?")

    def test_extractive_when(self):
        assert self._engine().is_extractive("When is the contract renewal date?")

    def test_extractive_total(self):
        assert self._engine().is_extractive("What is the total budget?")

    def test_descriptive_explain(self):
        assert not self._engine().is_extractive("Explain the system architecture")

    def test_descriptive_summarise(self):
        assert not self._engine().is_extractive("Summarise the key findings")

    def test_comparative_vs(self):
        assert self._engine().is_comparative("Compare document A versus document B")

    def test_comparative_difference(self):
        assert self._engine().is_comparative("What is the difference between the two?")

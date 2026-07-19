"""Evidence-Based Scientific Validation Engine (EBSVE) for CIEML 2.0.

Per-claim validators compute every pillar (statistical, practical, physical,
environmental) from upstream stage artifacts. Phase J: which claims run is owned
by an open claim pack (`cieml.claims` / `configs/claims/`); pillar algebra stays
in `HypothesisValidator`. Trace: classification → confidence → pillar scores →
EvidenceItem sources.
"""

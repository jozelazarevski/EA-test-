"""
Reference Checker — Matches questions to authoritative technical references.

Loads the reference knowledge base (YAML files) and provides relevant
ground-truth data to the LLM evaluator so it can fact-check EA responses
against authoritative public sources rather than relying solely on its own
training knowledge.

Key capabilities:
- Match scenarios/test cases to gold-standard expected answers
- Look up refrigerant properties, equipment specs, and safety standards
- Provide structured reference context for the evaluator prompt
- Tag which standards and regulations apply to a given question
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_REFERENCES_DIR = Path(__file__).parent / "references"


class ReferenceChecker:
    """Loads and queries the HVAC technical reference knowledge base."""

    def __init__(self, references_dir: str | Path | None = None) -> None:
        self._dir = Path(references_dir) if references_dir else _REFERENCES_DIR
        self._standards: dict[str, Any] = {}
        self._refrigerants: dict[str, Any] = {}
        self._equipment: dict[str, Any] = {}
        self._expected_answers: dict[str, Any] = {}
        self._jci_bas: dict[str, Any] = {}
        self._fire_safety: dict[str, Any] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._standards = self._load("hvac_standards.yaml")
        self._refrigerants = self._load("refrigerant_data.yaml")
        self._equipment = self._load("equipment_specs.yaml")
        self._expected_answers = self._load("expected_answers.yaml")
        self._jci_bas = self._load("jci_bas_documentation.yaml")
        self._fire_safety = self._load("fire_life_safety.yaml")
        self._loaded = True

    def _load(self, filename: str) -> dict:
        path = self._dir / filename
        if not path.exists():
            logger.warning("Reference file not found: %s", path)
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_scenario_reference(self, scenario_id: str) -> dict[str, Any] | None:
        """Get the gold-standard expected answer for a scenario."""
        self._ensure_loaded()
        scenarios = self._expected_answers.get("scenarios", {})
        return scenarios.get(scenario_id)

    def get_test_case_reference(self, test_id: str) -> dict[str, Any] | None:
        """Get the gold-standard expected answer for a static test case."""
        self._ensure_loaded()
        cases = self._expected_answers.get("test_cases", {})
        return cases.get(test_id)

    def get_refrigerant_data(self, refrigerant: str) -> dict[str, Any] | None:
        """Look up refrigerant properties by name (e.g. 'r410a', 'R-134a')."""
        self._ensure_loaded()
        key = refrigerant.lower().replace("-", "").replace(" ", "")
        refrigerants = self._refrigerants.get("refrigerants", {})
        return refrigerants.get(key)

    def get_diagnostic_reference(self, topic: str) -> dict[str, Any] | None:
        """Look up diagnostic reference (superheat, subcooling, approach, etc.)."""
        self._ensure_loaded()
        diag = self._refrigerants.get("diagnostic_reference", {})
        key = topic.lower().replace(" ", "_").replace("-", "_")
        return diag.get(key)

    def get_equipment_spec(self, model_key: str) -> dict[str, Any] | None:
        """Look up equipment specs (e.g. 'york_yk', 'york_yvaa')."""
        self._ensure_loaded()
        for category in ["chillers", "vfds", "controls", "rooftop_units"]:
            items = self._equipment.get(category, {})
            if model_key in items:
                return items[model_key]
        return None

    def get_safety_standards(self, *topics: str) -> list[dict[str, Any]]:
        """Get relevant safety standards for the given topics.

        Topics can be: 'refrigerant', 'electrical', 'confined_space',
        'lockout_tagout', 'epa', 'ventilation', etc.
        """
        self._ensure_loaded()
        results = []
        topic_set = {t.lower() for t in topics}

        # ASHRAE standards
        ashrae = self._standards.get("ashrae_standards", {})
        if topic_set & {"refrigerant", "chiller", "safety", "pressure"}:
            if "ashrae_15" in ashrae:
                results.append({"source": "ASHRAE 15", **ashrae["ashrae_15"]})
        if topic_set & {"energy", "efficiency", "chiller", "economizer"}:
            if "ashrae_90_1" in ashrae:
                results.append({"source": "ASHRAE 90.1", **ashrae["ashrae_90_1"]})
        if topic_set & {"ventilation", "outdoor_air", "ahu", "iad"}:
            if "ashrae_62_1" in ashrae:
                results.append({"source": "ASHRAE 62.1", **ashrae["ashrae_62_1"]})
        if topic_set & {"hospital", "healthcare", "medical"}:
            if "ashrae_170" in ashrae:
                results.append({"source": "ASHRAE 170", **ashrae["ashrae_170"]})

        # EPA
        epa = self._standards.get("epa_regulations", {})
        if topic_set & {"refrigerant", "epa", "leak", "recovery", "venting"}:
            if "section_608" in epa:
                results.append({"source": "EPA Section 608", **epa["section_608"]})

        # OSHA
        osha = self._standards.get("osha_guidelines", {})
        if topic_set & {"lockout_tagout", "loto", "electrical", "safety"}:
            if "lockout_tagout" in osha:
                results.append({"source": "OSHA LOTO", **osha["lockout_tagout"]})
        if topic_set & {"electrical", "vfd", "arc_flash"}:
            if "electrical_safety" in osha:
                results.append({"source": "OSHA Electrical", **osha["electrical_safety"]})
        if topic_set & {"confined_space", "ahu", "ductwork"}:
            if "confined_space" in osha:
                results.append({"source": "OSHA Confined Space", **osha["confined_space"]})

        # Fire & life safety (NFPA)
        nfpa = self._fire_safety.get("nfpa_standards", {})
        if topic_set & {"fire", "smoke", "fire_alarm", "sprinkler", "nfpa"}:
            if "nfpa_72" in nfpa:
                results.append({"source": "NFPA 72", **nfpa["nfpa_72"]})
            if "nfpa_13" in nfpa:
                results.append({"source": "NFPA 13", **nfpa["nfpa_13"]})
            if "nfpa_101" in nfpa:
                results.append({"source": "NFPA 101", **nfpa["nfpa_101"]})
        if topic_set & {"fire", "smoke", "ahu", "duct", "damper", "smoke_control"}:
            if "nfpa_90a" in nfpa:
                results.append({"source": "NFPA 90A", **nfpa["nfpa_90a"]})
            if "nfpa_80" in nfpa:
                results.append({"source": "NFPA 80", **nfpa["nfpa_80"]})

        # BAS-fire integration
        bas_fire = self._fire_safety.get("bas_fire_integration", {})
        if bas_fire and topic_set & {"fire", "smoke", "fire_alarm", "bas", "metasys", "controls"}:
            fire_warnings = bas_fire.get("safety_warnings", [])
            if fire_warnings:
                results.append({
                    "source": "JCI BAS-Fire Integration",
                    "title": "BAS and Fire Alarm System Integration",
                    "key_requirements": fire_warnings,
                })

        return results

    def get_jci_bas_reference(self, *topics: str) -> dict[str, Any]:
        """Get relevant JCI BAS documentation for the given topics.

        Topics: 'metasys', 'bacnet', 'mstp', 'nae', 'fec', 'controls',
        'ahu', 'vav', 'chiller_plant', 'facility_explorer', 'verasys',
        'commissioning', 'troubleshooting'.
        Source: https://docs.johnsoncontrols.com/bas/
        """
        self._ensure_loaded()
        if not self._jci_bas:
            return {}

        result: dict[str, Any] = {}
        topic_set = {t.lower() for t in topics}

        metasys = self._jci_bas.get("metasys", {})
        fx = self._jci_bas.get("facility_explorer", {})
        apps = self._jci_bas.get("hvac_applications", {})

        # Metasys / NAE / FEC / controls
        if topic_set & {"metasys", "nae", "fec", "controls", "bacnet", "mstp",
                        "bas", "building_automation", "n2"}:
            result["metasys_architecture"] = metasys.get("architecture", {})
            result["metasys_tools"] = metasys.get("tools", {})

        # BACnet MS/TP specifics
        if topic_set & {"bacnet", "mstp", "communication", "trunk", "wiring"}:
            protocols = metasys.get("architecture", {}).get("protocols", {})
            if "bacnet_mstp" in protocols:
                result["bacnet_mstp"] = protocols["bacnet_mstp"]

        # NAE troubleshooting
        if topic_set & {"nae", "metasys", "troubleshooting", "offline", "communication"}:
            result["metasys_troubleshooting"] = metasys.get("common_troubleshooting", {})

        # Commissioning
        if topic_set & {"commissioning", "startup", "setup"}:
            result["metasys_commissioning"] = metasys.get("commissioning_procedures", {})

        # Facility Explorer
        if topic_set & {"facility_explorer", "fx", "fx60", "fx80", "fx_zfr"}:
            result["facility_explorer"] = fx

        # Verasys
        if topic_set & {"verasys", "light_commercial", "thermostat"}:
            result["verasys"] = self._jci_bas.get("verasys", {})

        # HVAC application sequences
        if topic_set & {"chiller", "chiller_plant", "staging"}:
            if "chiller_plant_control" in apps:
                result["chiller_plant_control"] = apps["chiller_plant_control"]

        if topic_set & {"ahu", "air_handling", "economizer", "freezestat",
                        "discharge", "ventilation", "mixed_air"}:
            if "ahu_control" in apps:
                result["ahu_control"] = apps["ahu_control"]

        if topic_set & {"vav", "variable_air", "reheat", "zone"}:
            if "vav_box_control" in apps:
                result["vav_box_control"] = apps["vav_box_control"]

        # Integration protocols
        if topic_set & {"modbus", "lonworks", "lon", "integration", "protocol"}:
            result["integration_protocols"] = self._jci_bas.get("integration_protocols", {})

        return result

    def build_reference_context(
        self,
        *,
        scenario_id: str | None = None,
        test_id: str | None = None,
        question: str | None = None,
    ) -> str:
        """
        Build a formatted reference context string for the LLM evaluator.

        Automatically matches the scenario/test to gold-standard answers,
        relevant refrigerant data, equipment specs, and safety standards.

        Returns:
            A formatted string to inject into the evaluator prompt, or ""
            if no references match.
        """
        self._ensure_loaded()
        sections: list[str] = []

        # 1. Gold-standard expected answer
        expected = None
        if scenario_id:
            expected = self.get_scenario_reference(scenario_id)
        elif test_id:
            expected = self.get_test_case_reference(test_id)

        if expected:
            sections.append(self._format_expected_answer(expected))

        # 2. Detect relevant topics from question text
        topics = self._detect_topics(question or "", expected)

        # 3. Refrigerant data
        refrigerant = self._detect_refrigerant(question or "", expected)
        if refrigerant:
            ref_data = self.get_refrigerant_data(refrigerant)
            if ref_data:
                sections.append(self._format_refrigerant(refrigerant, ref_data))

        # 4. Equipment specs
        equipment = self._detect_equipment(question or "", expected)
        if equipment:
            spec = self.get_equipment_spec(equipment)
            if spec:
                sections.append(self._format_equipment(equipment, spec))

        # 5. Safety standards
        safety = self.get_safety_standards(*topics)
        if safety:
            sections.append(self._format_safety_standards(safety))

        # 6. JCI BAS documentation (docs.johnsoncontrols.com/bas/)
        jci_ref = self.get_jci_bas_reference(*topics)
        if jci_ref:
            sections.append(self._format_jci_bas(jci_ref))

        # 7. Fire/life safety & BAS-fire integration
        if topics & {"fire", "smoke", "fire_alarm", "smoke_control", "damper"}:
            fire_ctx = self._format_fire_safety(topics)
            if fire_ctx:
                sections.append(fire_ctx)

        if not sections:
            return ""

        return (
            "<reference_data>\n"
            "The following authoritative technical references should be used to "
            "fact-check the Expert Advisor's response. Compare specific claims, "
            "values, and procedures against these sources.\n\n"
            + "\n\n".join(sections)
            + "\n</reference_data>"
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_expected_answer(expected: dict) -> str:
        lines = ["## Gold-Standard Expected Answer"]
        title = expected.get("title") or expected.get("question", "")
        if title:
            lines.append(f"Topic: {title}")

        for section_key in ["required_elements", "expected_facts"]:
            data = expected.get(section_key)
            if not data:
                continue

            if isinstance(data, dict):
                for sub_key, items in data.items():
                    lines.append(f"\n### {sub_key.replace('_', ' ').title()}")
                    for item in items:
                        lines.append(f"  - {item}")
            elif isinstance(data, list):
                lines.append("\n### Expected Facts")
                for item in data:
                    lines.append(f"  - {item}")

        # Technical values
        for values_key in ["technical_values", "expected_values"]:
            values = expected.get(values_key, {})
            if values:
                lines.append("\n### Authoritative Technical Values")
                for k, v in values.items():
                    label = k.replace("_", " ").title()
                    lines.append(f"  - {label}: {v}")

        # Safety notes
        for safety_key in ["safety_warnings", "safety_notes"]:
            safety = expected.get(safety_key)
            if safety:
                lines.append("\n### Required Safety Warnings")
                for item in safety:
                    lines.append(f"  - {item}")

        # References
        refs = expected.get("references", [])
        if refs:
            lines.append("\n### Applicable Standards")
            for ref in refs:
                lines.append(f"  - {ref}")

        # Forbidden content
        forbidden = expected.get("forbidden_content", [])
        if forbidden:
            lines.append("\n### FORBIDDEN Content (red flag if present)")
            for item in forbidden:
                lines.append(f"  - {item}")

        return "\n".join(lines)

    @staticmethod
    def _format_refrigerant(name: str, data: dict) -> str:
        lines = [f"## Refrigerant Reference: {data.get('name', name.upper())}"]
        lines.append(f"Type: {data.get('type', 'N/A')}")
        lines.append(f"Safety group: {data.get('safety_group', 'N/A')}")
        lines.append(f"GWP: {data.get('gwp', 'N/A')}")

        pressures = data.get("operating_pressures", {})
        if pressures:
            lines.append("Operating pressures:")
            for k, v in pressures.items():
                lines.append(f"  - {k.replace('_', ' ').title()}: {v}")

        for key in ["normal_superheat_range_f", "normal_subcooling_range_f"]:
            val = data.get(key)
            if val:
                lines.append(f"{key.replace('_', ' ').title()}: {val}")

        lines.append(f"Oil compatibility: {data.get('oil_compatibility', 'N/A')}")

        charging = data.get("charging_method")
        if charging:
            lines.append(f"Charging method: {charging}")

        safety = data.get("safety_notes", [])
        if safety:
            lines.append("Safety notes:")
            for note in safety:
                lines.append(f"  - {note}")

        return "\n".join(lines)

    @staticmethod
    def _format_equipment(name: str, spec: dict) -> str:
        lines = [f"## Equipment Reference: {spec.get('manufacturer', '')} {spec.get('model_series', name)}"]

        for key in ["type", "compressor", "capacity_range_tons", "refrigerant"]:
            val = spec.get(key)
            if val:
                lines.append(f"{key.replace('_', ' ').title()}: {val}")

        for key in ["typical_full_load_kw_per_ton", "typical_iplv_kw_per_ton"]:
            val = spec.get(key)
            if val:
                lines.append(f"{key.replace('_', ' ').title()}: {val}")

        # Safety limits
        limits = spec.get("safety_limits", {})
        if limits:
            lines.append("Safety limits:")
            for k, v in limits.items():
                lines.append(f"  - {k.replace('_', ' ').title()}: {v}")

        return "\n".join(lines)

    @staticmethod
    def _format_safety_standards(standards: list[dict]) -> str:
        lines = ["## Applicable Safety Standards & Regulations"]
        for std in standards[:4]:  # Limit to avoid prompt bloat
            source = std.get("source", "Unknown")
            title = std.get("title", "")
            lines.append(f"\n### {source}: {title}")
            reqs = std.get("key_requirements") or std.get("requirements", [])
            for req in reqs[:6]:
                lines.append(f"  - {req}")
        return "\n".join(lines)

    @staticmethod
    def _format_jci_bas(jci_ref: dict) -> str:
        """Format JCI BAS documentation references.

        Source: https://docs.johnsoncontrols.com/bas/
        """
        lines = ["## Johnson Controls BAS Documentation"]
        lines.append("Source: docs.johnsoncontrols.com/bas/")

        # BACnet MS/TP
        mstp = jci_ref.get("bacnet_mstp", {})
        if mstp:
            specs = mstp.get("specifications", {})
            lines.append("\n### BACnet MS/TP Specifications (Metasys)")
            wiring = mstp.get("wiring", {})
            if wiring:
                lines.append(f"  - Wiring: {wiring.get('type', 'STP')}")
                lines.append(f"  - Topology: {wiring.get('topology', 'Daisy-chain')}")
                lines.append(f"  - Termination: {wiring.get('termination', '120 ohm')}")
                lines.append(f"  - Shield: {wiring.get('shield_grounding', 'One end only')}")
            if specs:
                lines.append(f"  - Max devices/trunk: {specs.get('max_devices_per_trunk', 32)}")
                lengths = specs.get("max_trunk_length", {})
                for baud_key, length in lengths.items():
                    lines.append(f"  - Max length {baud_key.replace('_', ' ')}: {length} ft")

            # Troubleshooting
            ts = mstp.get("troubleshooting", {})
            issues = ts.get("common_issues", [])
            if issues:
                lines.append("\n  Common MS/TP Issues:")
                for item in issues[:5]:
                    if isinstance(item, dict):
                        lines.append(f"  - {item.get('issue', '')}: {', '.join(item.get('causes', [])[:2])}")
                        lines.append(f"    Fix: {item.get('fix', '')}")
                    else:
                        lines.append(f"  - {item}")

        # Metasys architecture
        arch = jci_ref.get("metasys_architecture", {})
        if arch and not mstp:
            nae_info = arch.get("network_level", {}).get("nae", {})
            if nae_info:
                lines.append("\n### Metasys NAE (Network Automation Engine)")
                for model in nae_info.get("models", [])[:3]:
                    lines.append(f"  - {model.get('model', '')}: {model.get('description', '')}, max {model.get('max_points', '')} points")

        # Metasys troubleshooting
        ts_data = jci_ref.get("metasys_troubleshooting", {})
        if ts_data:
            lines.append("\n### Metasys Troubleshooting")
            for issue_key, issue_data in list(ts_data.items())[:3]:
                label = issue_key.replace("_", " ").title()
                lines.append(f"\n  {label}:")
                for check in issue_data.get("checks", [])[:4]:
                    lines.append(f"  - {check}")

        # AHU control sequences
        ahu = jci_ref.get("ahu_control", {})
        if ahu:
            lines.append("\n### AHU Control Sequences (Metasys/FX)")
            for seq in ahu.get("standard_sequences", [])[:5]:
                lines.append(f"  - {seq}")
            interlocks = ahu.get("safety_interlocks", [])
            if interlocks:
                lines.append("  Safety interlocks:")
                for il in interlocks[:4]:
                    lines.append(f"  - {il}")

        # VAV control
        vav = jci_ref.get("vav_box_control", {})
        if vav:
            lines.append("\n### VAV Box Control")
            modes = vav.get("control_modes", {})
            for mode, desc in modes.items():
                lines.append(f"  - {mode.title()}: {desc}")
            params = vav.get("key_parameters", [])
            if params:
                lines.append("  Key parameters:")
                for p in params[:5]:
                    lines.append(f"  - {p}")

        # Chiller plant control
        cp = jci_ref.get("chiller_plant_control", {})
        if cp:
            lines.append("\n### Chiller Plant Control")
            for feat in cp.get("key_features", [])[:5]:
                lines.append(f"  - {feat}")

        # Commissioning
        comm = jci_ref.get("metasys_commissioning", {})
        if comm:
            lines.append("\n### Metasys Commissioning Procedures")
            for phase, steps in list(comm.items())[:2]:
                label = phase.replace("_", " ").title()
                lines.append(f"\n  {label}:")
                for step in steps[:5]:
                    lines.append(f"  - {step}")

        # Facility Explorer
        fx_data = jci_ref.get("facility_explorer", {})
        if fx_data:
            lines.append(f"\n### Facility Explorer")
            lines.append(f"  {fx_data.get('description', '')}")
            controllers = fx_data.get("architecture", {}).get("field_controllers", {})
            for key, ctrl in list(controllers.items())[:3]:
                lines.append(f"  - {ctrl.get('name', key)}: {ctrl.get('description', '')}")

        return "\n".join(lines)

    def _format_fire_safety(self, topics: set[str]) -> str:
        """Format fire/life safety reference data."""
        lines = ["## Fire & Life Safety References"]

        bas_fire = self._fire_safety.get("bas_fire_integration", {})
        smoke_ctrl = self._fire_safety.get("smoke_control_systems", {})

        # BAS-fire integration
        if bas_fire and topics & {"fire", "bas", "metasys", "controls", "fire_alarm"}:
            lines.append("\n### BAS-Fire Alarm Integration")
            methods = bas_fire.get("integration_methods", {})
            hw = methods.get("hardwired", {})
            if hw:
                lines.append(f"  Primary method: {hw.get('description', 'Hardwired relays')}")
                for pt in hw.get("common_points", [])[:4]:
                    lines.append(f"  - {pt}")
                for note in hw.get("notes", [])[:3]:
                    lines.append(f"  NOTE: {note}")

            response = bas_fire.get("hvac_response_to_fire", {})
            general = response.get("general_alarm", [])
            if general:
                lines.append("\n  HVAC Response to Fire Alarm:")
                for step in general:
                    lines.append(f"  - {step}")

            cx = bas_fire.get("commissioning_fire_integration", [])
            if cx:
                lines.append("\n  Commissioning Fire Integration:")
                for step in cx[:5]:
                    lines.append(f"  - {step}")

        # Smoke control
        if smoke_ctrl and topics & {"smoke", "smoke_control", "stairwell", "pressurization"}:
            lines.append("\n### Smoke Control Systems")
            stair = smoke_ctrl.get("types", {}).get("stairwell_pressurization", {})
            if stair:
                lines.append("  Stairwell Pressurization:")
                for req in stair.get("requirements", [])[:4]:
                    lines.append(f"  - {req}")

        if len(lines) <= 1:
            return ""
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Topic / entity detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_topics(question: str, expected: dict | None) -> set[str]:
        """Detect relevant topic tags from the question text."""
        lower = question.lower()
        topics = set()

        keyword_map = {
            "refrigerant": ["refrigerant", "r-134a", "r-410a", "r-22", "r134a", "r410a",
                            "charge", "superheat", "subcooling", "leak"],
            "chiller": ["chiller", "centrifugal", "screw", "evaporator", "condenser",
                        "head pressure", "suction pressure", "york yk", "york yvaa"],
            "safety": ["safety", "danger", "hazard", "loto", "lockout", "arc flash",
                       "pressure", "relief", "emergency"],
            "electrical": ["vfd", "drive", "motor", "amps", "voltage", "electrical",
                          "overcurrent", "igbt", "arc flash"],
            "ventilation": ["ahu", "air handling", "outdoor air", "ventilation",
                           "damper", "economizer", "mixed air"],
            "epa": ["epa", "section 608", "recovery", "venting", "leak rate",
                    "certification", "refrigerant"],
            "lockout_tagout": ["loto", "lockout", "tagout", "isolation", "zero energy"],
            "hospital": ["hospital", "medical", "healthcare", "patient", "operating room"],
            "metasys": ["metasys", "nae", "nce", "sct", "smp", "ads", "adx"],
            "bacnet": ["bacnet", "mstp", "ms/tp", "trunk", "mac address"],
            "controls": ["controls", "bas", "building automation", "ddc", "sequence"],
            "ahu": ["ahu", "air handling", "discharge air", "mixed air", "preheat",
                    "freezestat", "economizer"],
            "vav": ["vav", "variable air volume", "reheat", "zone control", "damper"],
            "chiller_plant": ["chiller plant", "staging", "lead lag", "condenser water reset"],
            "facility_explorer": ["facility explorer", "fx60", "fx80", "fx-zfr", "fx supervisor"],
            "commissioning": ["commissioning", "startup", "commission", "cx"],
            "troubleshooting": ["troubleshoot", "diagnos", "fault", "alarm", "offline", "error"],
            "fire": ["fire", "smoke", "fire alarm", "fire damper", "smoke detector",
                     "fire suppression", "nfpa", "sprinkler"],
            "modbus": ["modbus", "modbus rtu", "modbus tcp"],
        }

        for topic, keywords in keyword_map.items():
            if any(kw in lower for kw in keywords):
                topics.add(topic)

        # Also pull tags from expected answer
        if expected:
            tags = expected.get("tags", [])
            for tag in tags:
                topics.add(tag.lower().replace("-", "_"))

        return topics

    @staticmethod
    def _detect_refrigerant(question: str, expected: dict | None) -> str | None:
        """Detect which refrigerant is relevant."""
        lower = question.lower()
        for ref in ["r410a", "r134a", "r22", "r513a", "r1234ze"]:
            if ref in lower.replace("-", "").replace(" ", ""):
                return ref

        # Check expected answer for refrigerant references
        if expected:
            values = expected.get("technical_values", {}) or expected.get("expected_values", {})
            for k, v in values.items():
                if "r410a" in str(v).lower().replace("-", ""):
                    return "r410a"
                if "r134a" in str(v).lower().replace("-", ""):
                    return "r134a"
            refrigerant = str(values.get("refrigerant", "")).lower().replace("-", "")
            if refrigerant:
                return refrigerant

        return None

    @staticmethod
    def _detect_equipment(question: str, expected: dict | None) -> str | None:
        """Detect which equipment model is relevant."""
        lower = question.lower()
        equipment_map = {
            "york_yk": ["york yk", "yk chiller", "yk series"],
            "york_yvaa": ["york yvaa", "yvaa"],
            "metasys": ["metasys", "nae", "fec", "bacnet"],
            "general_specifications": ["vfd", "variable frequency", "drive"],
        }
        for key, patterns in equipment_map.items():
            if any(p in lower for p in patterns):
                return key
        return None

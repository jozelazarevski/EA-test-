"""
HVAC Test Cases for Expert Advisor Testing Agent.

Standalone test cases:
- id: Unique identifier
- category: HVAC domain category
- question: The question to ask Expert Advisor
- expect_pdf: Whether a PDF/document link is expected
- pdf_keywords: Keywords expected inside referenced PDFs
- test_type: Optional type hint for edge-case handling

Conversation chains:
- id: Unique chain identifier
- category: HVAC domain category
- topic: Short description of the equipment/scenario under test
- description: What the chain is testing
- questions: Ordered list of questions sent consecutively (same session)
"""

TEST_CASES = [
    # --- Category: Chiller Systems ---
    {
        "id": "CHILLER-001",
        "category": "Chiller Systems",
        "question": "What are the common causes of low evaporator pressure in a centrifugal chiller?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "CHILLER-002",
        "category": "Chiller Systems",
        "question": "How do I troubleshoot a York YK chiller with high condenser pressure?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "CHILLER-003",
        "category": "Chiller Systems",
        "question": "What is the recommended maintenance schedule for a Johnson Controls YORK YVAA chiller?",
        "expect_pdf": True,
        "pdf_keywords": ["maintenance", "schedule"],
    },
    # --- Category: Air Handling Units ---
    {
        "id": "AHU-001",
        "category": "Air Handling Units",
        "question": "What are the steps to commission a new air handling unit?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "AHU-002",
        "category": "Air Handling Units",
        "question": "How do I balance airflow in a VAV system with multiple zones?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    # --- Category: Controls & BAS ---
    {
        "id": "CTRL-001",
        "category": "Controls & BAS",
        "question": "How do I configure a PID loop for discharge air temperature control in a Metasys system?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "CTRL-002",
        "category": "Controls & BAS",
        "question": "What are the network requirements for connecting BACnet controllers to a Metasys server?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    # --- Category: Refrigeration ---
    {
        "id": "REF-001",
        "category": "Refrigeration",
        "question": "What refrigerant is used in the YORK YVFA chiller and what are its safety considerations?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "REF-002",
        "category": "Refrigeration",
        "question": "How do I perform a refrigerant leak test on a chiller system?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    # --- Category: Energy Efficiency ---
    {
        "id": "ENERGY-001",
        "category": "Energy Efficiency",
        "question": "What are the best practices to improve chiller plant energy efficiency?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "ENERGY-002",
        "category": "Energy Efficiency",
        "question": "How does variable speed drive technology improve HVAC system performance?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    # --- Category: Fire & Safety ---
    {
        "id": "SAFETY-001",
        "category": "Fire & Safety",
        "question": "What are the fire safety requirements for HVAC ductwork installations?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    # --- Category: Product Documentation ---
    {
        "id": "DOC-001",
        "category": "Product Documentation",
        "question": "Can you provide the installation guide for the YORK YZ magnetic bearing centrifugal chiller?",
        "expect_pdf": True,
        "pdf_keywords": ["installation", "YZ"],
    },
    {
        "id": "DOC-002",
        "category": "Product Documentation",
        "question": "Where can I find the technical specifications for Johnson Controls Metasys controllers?",
        "expect_pdf": True,
        "pdf_keywords": ["Metasys"],
    },
    # --- Category: Troubleshooting ---
    {
        "id": "TSHOOT-001",
        "category": "Troubleshooting",
        "question": "My chiller is showing a high discharge temperature alarm. What should I check first?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    {
        "id": "TSHOOT-002",
        "category": "Troubleshooting",
        "question": "The compressor on my rooftop unit is short cycling. How do I diagnose the issue?",
        "expect_pdf": False,
        "pdf_keywords": [],
    },
    # --- Category: Edge Cases & Stress Tests ---
    {
        "id": "EDGE-001",
        "category": "Edge Cases",
        "question": "What is the meaning of life?",
        "expect_pdf": False,
        "pdf_keywords": [],
        "test_type": "off_topic",
    },
    {
        "id": "EDGE-002",
        "category": "Edge Cases",
        "question": "Compare Johnson Controls chillers with Carrier and Trane chillers.",
        "expect_pdf": False,
        "pdf_keywords": [],
        "test_type": "competitor",
    },
    {
        "id": "EDGE-003",
        "category": "Edge Cases",
        "question": "",
        "expect_pdf": False,
        "pdf_keywords": [],
        "test_type": "empty_input",
    },
]


# ---------------------------------------------------------------------------
# Conversation Chains — consecutive questions that must stay coherent
# ---------------------------------------------------------------------------

CONVERSATION_CHAINS = [
    {
        "id": "CHAIN-YK-001",
        "category": "Chiller Systems",
        "topic": "YORK YK Centrifugal Chiller",
        "description": (
            "Consecutive troubleshooting questions about a YORK YK chiller. "
            "Verifies that Expert Advisor maintains context about the same "
            "chiller model, refrigerant type (R-134a), and operating parameters "
            "across the full conversation."
        ),
        "questions": [
            "What refrigerant does the YORK YK centrifugal chiller use and what are its normal operating pressures?",
            "The head pressure on this chiller is running about 15 PSI above normal. What should I check first?",
            "I checked the condenser water and it looks fine. Could a problem with the VFD on the condenser water pump cause this?",
            "What is the recommended purge unit maintenance schedule for this chiller?",
        ],
    },
    {
        "id": "CHAIN-YVAA-001",
        "category": "Chiller Systems",
        "topic": "YORK YVAA Air-Cooled Screw Chiller",
        "description": (
            "Progressive maintenance and diagnostics conversation about a "
            "YORK YVAA chiller. Checks that EA keeps answers specific to the "
            "YVAA model (air-cooled, screw compressor, R-410A) and does not "
            "drift to other chiller types."
        ),
        "questions": [
            "What are the key maintenance items for a YORK YVAA air-cooled screw chiller?",
            "How often should the compressor oil be analyzed on this unit?",
            "The chiller is showing a low suction pressure alarm. What are the most likely causes for this specific model?",
            "Can I use R-410A recovery equipment that I also use for residential systems on this chiller?",
        ],
    },
    {
        "id": "CHAIN-METASYS-001",
        "category": "Controls & BAS",
        "topic": "Metasys BACnet Integration",
        "description": (
            "Multi-step troubleshooting of a BACnet MS/TP communication issue "
            "on a Metasys system. Verifies that EA tracks the problem context "
            "(NAE, trunk, device addressing) across turns without losing the thread."
        ),
        "questions": [
            "I have a Metasys NAE that has lost communication with several field controllers on a BACnet MS/TP trunk. Where do I start troubleshooting?",
            "I checked the wiring and it looks intact. The trunk has 24 devices. Could the trunk length be an issue?",
            "What is the maximum recommended trunk length for BACnet MS/TP at 76800 baud on a Metasys system?",
            "Some devices came back online but three are still offline. They are all on the far end of the trunk. What should I check next?",
        ],
    },
    {
        "id": "CHAIN-AHU-001",
        "category": "Air Handling Units",
        "topic": "AHU Freezestat Trip Diagnosis",
        "description": (
            "Step-by-step diagnosis of a freezestat trip on an air handling unit. "
            "Tests that EA maintains the equipment context (mixed air section, "
            "hot water coil, outdoor air damper) and builds on previous answers."
        ),
        "questions": [
            "My air handling unit tripped on a freezestat alarm this morning. The outdoor temperature was 28°F. What are the common causes?",
            "The hot water coil valve was stuck partially closed. Could this alone cause a freezestat trip?",
            "I fixed the valve but want to prevent this from happening again. What control sequence changes should I make?",
            "Should I also add a low-limit safety on the mixed air temperature? What setpoint would you recommend?",
        ],
    },
]

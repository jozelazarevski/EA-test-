"""
HVAC Test Cases for Expert Advisor Testing Agent.

Each test case contains:
- id: Unique identifier
- category: HVAC domain category
- question: The question to ask Expert Advisor
- expect_pdf: Whether a PDF/document link is expected
- pdf_keywords: Keywords expected inside referenced PDFs
- test_type: Optional type hint for edge-case handling
    ("off_topic", "competitor", "empty_input")
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

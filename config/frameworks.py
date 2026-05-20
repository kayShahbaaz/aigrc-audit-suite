"""
config/frameworks.py — AI GRC Audit Suite
============================================
Single source of truth for ALL Saudi Arabia GRC frameworks.

Contains:
- Framework metadata (name, description, who it applies to)
- Control domains per framework
- Individual controls per domain (used by Modules 3, 4, 12, 13)
- Policy types per framework (used by Module 1)

Phase 1: Saudi Arabia only.
Phase 2: UAE frameworks will be added here.
Phase 3: India frameworks will be added here.

Coding rule: All modules import from here — never hardcode framework names in modules.
"""

# =============================================================
# FRAMEWORK REGISTRY
# Master list of all supported frameworks.
# Used by the UI dropdowns throughout the app.
# =============================================================

FRAMEWORKS = {
    "NCA_ECC": {
        "id": "NCA_ECC",
        "name": "NCA ECC",
        "full_name": "Essential Cybersecurity Controls",
        "authority": "National Cybersecurity Authority (NCA)",
        "region": "Saudi Arabia",
        "applies_to": "All Saudi organizations — mandatory for government and critical sectors",
        "description": (
            "The NCA ECC is the foundational cybersecurity framework for Saudi Arabia. "
            "It defines essential controls that all organizations operating in the Kingdom "
            "must implement. Compliance is mandatory for government entities and strongly "
            "recommended for private sector organizations."
        ),
    },
    "NCA_CCC": {
        "id": "NCA_CCC",
        "name": "NCA CCC",
        "full_name": "Cloud Cybersecurity Controls",
        "authority": "National Cybersecurity Authority (NCA)",
        "region": "Saudi Arabia",
        "applies_to": "Cloud service providers operating in or serving Saudi Arabia",
        "description": (
            "The NCA CCC provides cybersecurity requirements specifically for cloud "
            "environments. Applies to cloud service providers and organizations that "
            "host data or services in the cloud within the Saudi regulatory perimeter."
        ),
    },
    "NCA_CSCC": {
        "id": "NCA_CSCC",
        "name": "NCA CSCC",
        "full_name": "Cybersecurity Controls for Critical Sectors",
        "authority": "National Cybersecurity Authority (NCA)",
        "region": "Saudi Arabia",
        "applies_to": "Critical infrastructure — energy, water, transport, healthcare",
        "description": (
            "Enhanced cybersecurity controls for organizations operating in critical "
            "national infrastructure sectors. Builds on ECC with additional requirements "
            "for sectors where a cyber incident could have national impact."
        ),
    },
    "SAMA_CSF": {
        "id": "SAMA_CSF",
        "name": "SAMA CSF",
        "full_name": "Cybersecurity Framework",
        "authority": "Saudi Arabian Monetary Authority (SAMA)",
        "region": "Saudi Arabia",
        "applies_to": "Banks, NBFCs, insurance companies, and all SAMA-regulated financial institutions",
        "description": (
            "SAMA CSF is the mandatory cybersecurity framework for all financial "
            "institutions regulated by the Saudi Central Bank. It covers governance, "
            "risk management, operations, and resilience for the financial sector."
        ),
    },
    "SAMA_BCM": {
        "id": "SAMA_BCM",
        "name": "SAMA BCM",
        "full_name": "Business Continuity Management Framework",
        "authority": "Saudi Arabian Monetary Authority (SAMA)",
        "region": "Saudi Arabia",
        "applies_to": "All SAMA-regulated entities",
        "description": (
            "SAMA BCM defines business continuity requirements for financial institutions. "
            "Covers BCM governance, business impact analysis, continuity strategies, "
            "testing, and crisis communication requirements."
        ),
    },
    "SDAIA_PDPL": {
        "id": "SDAIA_PDPL",
        "name": "SDAIA PDPL",
        "full_name": "Personal Data Protection Law",
        "authority": "Saudi Data and Artificial Intelligence Authority (SDAIA)",
        "region": "Saudi Arabia",
        "applies_to": "Every organization that collects, processes, or stores personal data of Saudi residents",
        "description": (
            "Saudi Arabia's Personal Data Protection Law — the Kingdom's equivalent of GDPR. "
            "Mandatory for any entity handling personal data of individuals in Saudi Arabia. "
            "Governs collection, processing, storage, sharing, and deletion of personal data."
        ),
    },
    "CITC": {
        "id": "CITC",
        "name": "CITC",
        "full_name": "Communications and Information Technology Commission Guidelines",
        "authority": "Communications, Space and Technology Commission (CST, formerly CITC)",
        "region": "Saudi Arabia",
        "applies_to": "Telecom operators, internet service providers, and ICT companies",
        "description": (
            "CITC/CST cybersecurity guidelines apply to telecommunications and information "
            "technology companies operating in Saudi Arabia. Covers network security, "
            "subscriber data protection, and service continuity requirements."
        ),
    },
    "VISION_2030": {
        "id": "VISION_2030",
        "name": "Vision 2030",
        "full_name": "Vision 2030 Digital Transformation Cybersecurity Requirements",
        "authority": "Kingdom of Saudi Arabia — Vision 2030 Program",
        "region": "Saudi Arabia",
        "applies_to": "Government entities and organizations aligned with Vision 2030 programs",
        "description": (
            "Cybersecurity requirements tied to Saudi Arabia's Vision 2030 digital "
            "transformation agenda. Applies to government agencies and companies "
            "participating in Vision 2030 projects and national transformation programs."
        ),
    },
}


# =============================================================
# NCA ECC — CONTROL DOMAINS AND CONTROLS
# Source: NCA ECC v1.0 (2018), updated controls
# =============================================================

NCA_ECC_CONTROLS = {
    "1-Cybersecurity_Governance": {
        "domain_id": "1",
        "domain_name": "Cybersecurity Governance",
        "controls": [
            {"id": "1-1", "name": "Cybersecurity Leadership and Oversight", "description": "Establish cybersecurity leadership including CISO role and board-level oversight of cybersecurity risks."},
            {"id": "1-2", "name": "Cybersecurity Strategy", "description": "Develop, approve, and implement a documented cybersecurity strategy aligned to the organization's objectives."},
            {"id": "1-3", "name": "Cybersecurity Policies and Procedures", "description": "Establish, approve, and implement a comprehensive set of cybersecurity policies and procedures."},
            {"id": "1-4", "name": "Cybersecurity Roles and Responsibilities", "description": "Define and document cybersecurity roles and responsibilities across the organization."},
            {"id": "1-5", "name": "Cybersecurity Risk Management", "description": "Implement a risk management process to identify, assess, treat, and monitor cybersecurity risks."},
        ],
    },
    "2-Cybersecurity_Risk_Management": {
        "domain_id": "2",
        "domain_name": "Cybersecurity Risk Management",
        "controls": [
            {"id": "2-1", "name": "Asset Management", "description": "Identify and maintain an inventory of all information assets including hardware, software, and data."},
            {"id": "2-2", "name": "Risk Assessment", "description": "Conduct regular cybersecurity risk assessments to identify threats, vulnerabilities, and potential impacts."},
            {"id": "2-3", "name": "Risk Treatment", "description": "Define and implement risk treatment plans for identified cybersecurity risks within acceptable risk appetite."},
            {"id": "2-4", "name": "Compliance Management", "description": "Monitor and ensure compliance with applicable cybersecurity laws, regulations, and contractual requirements."},
        ],
    },
    "3-Cybersecurity_Operations": {
        "domain_id": "3",
        "domain_name": "Cybersecurity Operations",
        "controls": [
            {"id": "3-1", "name": "Identity and Access Management", "description": "Implement controls to manage user identities and control access to systems and data based on least privilege."},
            {"id": "3-2", "name": "Network Security", "description": "Implement network security controls including segmentation, firewalls, and monitoring of network traffic."},
            {"id": "3-3", "name": "Endpoint Security", "description": "Protect endpoints including servers, workstations, and mobile devices with appropriate security controls."},
            {"id": "3-4", "name": "Application Security", "description": "Implement security throughout the application development lifecycle and protect applications in production."},
            {"id": "3-5", "name": "Data and Information Protection", "description": "Classify, label, and protect data throughout its lifecycle including storage, processing, and transmission."},
            {"id": "3-6", "name": "Cryptography", "description": "Implement cryptographic controls to protect data confidentiality and integrity."},
            {"id": "3-7", "name": "Physical and Environmental Security", "description": "Protect physical access to information processing facilities and protect against environmental threats."},
            {"id": "3-8", "name": "Vulnerability Management", "description": "Identify, assess, and remediate technical vulnerabilities in systems and applications in a timely manner."},
            {"id": "3-9", "name": "Change Management", "description": "Control changes to IT systems through a formal change management process to prevent security degradation."},
            {"id": "3-10", "name": "Backup and Recovery", "description": "Implement regular backups of critical data and test recovery procedures to ensure business continuity."},
        ],
    },
    "4-Third_Party_Cybersecurity": {
        "domain_id": "4",
        "domain_name": "Third-Party and Supply Chain Cybersecurity",
        "controls": [
            {"id": "4-1", "name": "Third-Party Risk Management", "description": "Assess and manage cybersecurity risks introduced by third-party vendors, suppliers, and service providers."},
            {"id": "4-2", "name": "Outsourcing Security", "description": "Ensure cybersecurity requirements are defined and enforced in outsourcing arrangements and contracts."},
            {"id": "4-3", "name": "Cloud Computing Security", "description": "Apply appropriate security controls when using cloud services, including data protection and access controls."},
        ],
    },
    "5-Cybersecurity_Resilience": {
        "domain_id": "5",
        "domain_name": "Cybersecurity Resilience",
        "controls": [
            {"id": "5-1", "name": "Business Continuity Management", "description": "Integrate cybersecurity into business continuity planning to maintain operations during and after cyber incidents."},
            {"id": "5-2", "name": "Disaster Recovery", "description": "Develop and test disaster recovery plans for critical systems affected by cyber incidents."},
            {"id": "5-3", "name": "Incident Management", "description": "Establish a cybersecurity incident management capability to detect, respond to, and recover from incidents."},
        ],
    },
    "6-Cybersecurity_Awareness": {
        "domain_id": "6",
        "domain_name": "Cybersecurity Awareness and Training",
        "controls": [
            {"id": "6-1", "name": "Cybersecurity Awareness Program", "description": "Implement an ongoing cybersecurity awareness program for all staff covering threats, policies, and safe practices."},
            {"id": "6-2", "name": "Specialized Cybersecurity Training", "description": "Provide role-specific cybersecurity training for staff with cybersecurity responsibilities."},
        ],
    },
}


# =============================================================
# SAMA CSF — CONTROL DOMAINS AND CONTROLS
# Source: SAMA Cyber Security Framework v1.0 (2017)
# =============================================================

SAMA_CSF_CONTROLS = {
    "1-Cyber_Security_Leadership": {
        "domain_id": "1",
        "domain_name": "Cyber Security Leadership and Governance",
        "controls": [
            {"id": "1.1", "name": "Cyber Security Strategy", "description": "Establish and maintain a formal cyber security strategy approved by senior management."},
            {"id": "1.2", "name": "Cyber Security Framework", "description": "Develop and implement a cyber security framework covering all critical aspects of information security."},
            {"id": "1.3", "name": "Cyber Security Policies", "description": "Create, approve, and enforce comprehensive cyber security policies aligned to regulatory requirements."},
            {"id": "1.4", "name": "Cyber Security Roles", "description": "Define CISO role and all cyber security responsibilities with clear reporting lines to senior management."},
            {"id": "1.5", "name": "Cyber Security Budget", "description": "Allocate adequate budget for cyber security operations, tools, and human resources."},
        ],
    },
    "2-Cyber_Security_Risk_Management": {
        "domain_id": "2",
        "domain_name": "Cyber Security Risk Management and Compliance",
        "controls": [
            {"id": "2.1", "name": "Risk Identification", "description": "Maintain a current inventory of assets and identify cyber security risks associated with each asset."},
            {"id": "2.2", "name": "Risk Assessment", "description": "Conduct regular risk assessments using a defined methodology covering likelihood and impact."},
            {"id": "2.3", "name": "Risk Treatment", "description": "Define and implement risk treatment plans with owners, timelines, and residual risk acceptance."},
            {"id": "2.4", "name": "Regulatory Compliance", "description": "Monitor compliance with SAMA regulations, NCA requirements, and other applicable cybersecurity laws."},
        ],
    },
    "3-Cyber_Security_Operations": {
        "domain_id": "3",
        "domain_name": "Cyber Security Operations and Technology",
        "controls": [
            {"id": "3.1", "name": "Identity and Access Management", "description": "Implement strong IAM controls including multi-factor authentication for privileged and remote access."},
            {"id": "3.2", "name": "Network Security", "description": "Segment networks and monitor traffic to detect and prevent unauthorized access and lateral movement."},
            {"id": "3.3", "name": "Endpoint Protection", "description": "Deploy endpoint security solutions and maintain hardened configurations on all devices."},
            {"id": "3.4", "name": "Data Loss Prevention", "description": "Implement DLP controls to detect and prevent unauthorized transmission of sensitive financial data."},
            {"id": "3.5", "name": "Security Monitoring and SOC", "description": "Operate or contract a Security Operations Center with 24x7 monitoring capability."},
            {"id": "3.6", "name": "Vulnerability and Patch Management", "description": "Maintain a vulnerability management program with defined patching SLAs based on criticality."},
            {"id": "3.7", "name": "Penetration Testing", "description": "Conduct regular penetration testing of critical systems including customer-facing applications."},
        ],
    },
    "4-Third_Party_Management": {
        "domain_id": "4",
        "domain_name": "Third-Party Management",
        "controls": [
            {"id": "4.1", "name": "Vendor Security Assessment", "description": "Assess cyber security posture of all vendors with access to financial systems or customer data."},
            {"id": "4.2", "name": "Contractual Security Requirements", "description": "Include cyber security requirements in all vendor contracts covering data protection and incident reporting."},
            {"id": "4.3", "name": "Outsourcing Oversight", "description": "Maintain oversight of outsourced functions including regular audits and performance monitoring."},
        ],
    },
    "5-Cyber_Resilience": {
        "domain_id": "5",
        "domain_name": "Cyber Resilience",
        "controls": [
            {"id": "5.1", "name": "Business Continuity Planning", "description": "Integrate cyber scenarios into BCP and ensure critical financial services can continue during incidents."},
            {"id": "5.2", "name": "Incident Response", "description": "Maintain an incident response plan and team with defined escalation and SAMA notification procedures."},
            {"id": "5.3", "name": "Crisis Management", "description": "Establish crisis management procedures for major cyber incidents affecting financial services."},
            {"id": "5.4", "name": "Recovery Testing", "description": "Test BCPs and disaster recovery plans annually at minimum, including cyber-specific scenarios."},
        ],
    },
}


# =============================================================
# SDAIA PDPL — CONTROL DOMAINS AND CONTROLS
# Source: Saudi Personal Data Protection Law (PDPL) 2021
# =============================================================

SDAIA_PDPL_CONTROLS = {
    "1-Data_Governance": {
        "domain_id": "1",
        "domain_name": "Data Protection Governance",
        "controls": [
            {"id": "PDPL-1.1", "name": "Data Protection Officer", "description": "Appoint a Data Protection Officer (DPO) responsible for PDPL compliance oversight."},
            {"id": "PDPL-1.2", "name": "Data Protection Policy", "description": "Establish and publish a comprehensive personal data protection policy."},
            {"id": "PDPL-1.3", "name": "Records of Processing Activities", "description": "Maintain a register of all personal data processing activities including purposes, categories, and legal bases."},
        ],
    },
    "2-Lawful_Processing": {
        "domain_id": "2",
        "domain_name": "Lawful Basis for Processing",
        "controls": [
            {"id": "PDPL-2.1", "name": "Consent Management", "description": "Obtain valid, informed, and explicit consent before collecting personal data; maintain consent records."},
            {"id": "PDPL-2.2", "name": "Purpose Limitation", "description": "Collect personal data only for specified, explicit, and legitimate purposes; do not process beyond stated purposes."},
            {"id": "PDPL-2.3", "name": "Data Minimization", "description": "Collect only personal data that is adequate and limited to what is necessary for the processing purpose."},
        ],
    },
    "3-Data_Subject_Rights": {
        "domain_id": "3",
        "domain_name": "Data Subject Rights",
        "controls": [
            {"id": "PDPL-3.1", "name": "Right of Access", "description": "Provide data subjects with access to their personal data upon request within the legal timeframe."},
            {"id": "PDPL-3.2", "name": "Right to Correction", "description": "Correct inaccurate personal data upon request by the data subject."},
            {"id": "PDPL-3.3", "name": "Right to Erasure", "description": "Delete personal data upon request when legal basis for processing no longer exists."},
            {"id": "PDPL-3.4", "name": "Right to Withdraw Consent", "description": "Allow data subjects to withdraw consent at any time and cease processing accordingly."},
        ],
    },
    "4-Data_Security": {
        "domain_id": "4",
        "domain_name": "Personal Data Security",
        "controls": [
            {"id": "PDPL-4.1", "name": "Technical Security Measures", "description": "Implement appropriate technical measures to protect personal data against unauthorized access, loss, or destruction."},
            {"id": "PDPL-4.2", "name": "Encryption of Personal Data", "description": "Encrypt personal data in transit and at rest using industry-standard cryptographic controls."},
            {"id": "PDPL-4.3", "name": "Access Controls for Personal Data", "description": "Restrict access to personal data on a need-to-know basis with strong authentication."},
        ],
    },
    "5-Breach_Management": {
        "domain_id": "5",
        "domain_name": "Data Breach Management",
        "controls": [
            {"id": "PDPL-5.1", "name": "Breach Detection and Response", "description": "Implement procedures to detect, contain, and respond to personal data breaches."},
            {"id": "PDPL-5.2", "name": "Breach Notification to SDAIA", "description": "Notify SDAIA of personal data breaches within 72 hours of becoming aware of the breach."},
            {"id": "PDPL-5.3", "name": "Breach Notification to Data Subjects", "description": "Notify affected data subjects when a breach is likely to result in high risk to their rights."},
        ],
    },
    "6-Cross_Border_Transfers": {
        "domain_id": "6",
        "domain_name": "Cross-Border Data Transfers",
        "controls": [
            {"id": "PDPL-6.1", "name": "Transfer Restriction", "description": "Do not transfer personal data outside Saudi Arabia without appropriate legal basis or SDAIA approval."},
            {"id": "PDPL-6.2", "name": "Adequate Protection Requirement", "description": "Ensure receiving country provides adequate personal data protection before transfer."},
        ],
    },
    "7-Data_Retention": {
        "domain_id": "7",
        "domain_name": "Data Retention and Disposal",
        "controls": [
            {"id": "PDPL-7.1", "name": "Retention Policy", "description": "Define and enforce personal data retention periods aligned to business need and legal requirements."},
            {"id": "PDPL-7.2", "name": "Secure Disposal", "description": "Securely delete or anonymize personal data when the retention period expires."},
        ],
    },
}


# =============================================================
# POLICY TYPES PER FRAMEWORK
# Used by Module 1 — Policy Generator
# Maps each framework to the policies an auditor typically produces
# =============================================================

POLICY_TYPES = {
    "NCA_ECC": [
        "Acceptable Use Policy",
        "Access Control Policy",
        "Asset Management Policy",
        "Incident Response Policy",
        "Third-Party Security Policy",
        "Remote Work Security Policy",
        "Password Management Policy",
        "Data Classification Policy",
        "Physical Security Policy",
        "Vulnerability Management Policy",
        "Change Management Policy",
        "Backup and Recovery Policy",
    ],
    "SAMA_CSF": [
        "Cyber Security Governance Policy",
        "Identity and Access Management Policy",
        "Threat and Vulnerability Management Policy",
        "Cyber Resilience and BCP Policy",
        "Third-Party and Outsourcing Security Policy",
        "Data Loss Prevention Policy",
        "Security Monitoring Policy",
        "Penetration Testing Policy",
    ],
    "SDAIA_PDPL": [
        "Personal Data Processing Policy",
        "Consent Management Policy",
        "Data Subject Rights Procedure",
        "Data Breach Response Policy",
        "Data Retention and Disposal Policy",
        "Cross-Border Data Transfer Policy",
        "Privacy Notice Template",
    ],
    "NCA_CCC": [
        "Cloud Security Policy",
        "Cloud Data Protection Policy",
        "Cloud Access Management Policy",
        "Cloud Vendor Assessment Policy",
    ],
    "NCA_CSCC": [
        "Critical Infrastructure Protection Policy",
        "Operational Technology Security Policy",
        "Industrial Control Systems Security Policy",
    ],
    "SAMA_BCM": [
        "Business Continuity Policy",
        "Business Impact Analysis Procedure",
        "Crisis Communication Policy",
        "DR Testing Policy",
    ],
    "CITC": [
        "Telecom Network Security Policy",
        "Subscriber Data Protection Policy",
        "Service Continuity Policy",
    ],
    "VISION_2030": [
        "Digital Transformation Security Policy",
        "Government Data Security Policy",
        "E-Government Services Security Policy",
    ],
}


# =============================================================
# CONTROLS LOOKUP — maps framework ID to its controls dict
# Used by Modules 3 and 4 to get controls for any framework
# =============================================================

FRAMEWORK_CONTROLS = {
    "NCA_ECC": NCA_ECC_CONTROLS,
    "SAMA_CSF": SAMA_CSF_CONTROLS,
    "SDAIA_PDPL": SDAIA_PDPL_CONTROLS,
    # NCA_CCC, NCA_CSCC, SAMA_BCM, CITC, VISION_2030 controls
    # will be added in future iterations — enough for Phase 1 MVP
}


# =============================================================
# HELPER FUNCTIONS
# =============================================================

def get_framework_list() -> list:
    """
    Return a list of (id, display_name) tuples for all frameworks.
    Used to populate framework dropdown menus in the UI.
    """
    return [(fw_id, fw["name"] + " — " + fw["full_name"])
            for fw_id, fw in FRAMEWORKS.items()]


def get_framework_by_id(framework_id: str) -> dict:
    """
    Return the full framework metadata dict for a given framework ID.
    Returns None if framework ID is not found.
    """
    return FRAMEWORKS.get(framework_id)


def get_controls_for_framework(framework_id: str) -> dict:
    """
    Return all control domains and controls for a given framework.
    Returns empty dict if framework has no controls defined yet.
    Used by Module 3 (checklist) and Module 4 (gap assessment).
    """
    return FRAMEWORK_CONTROLS.get(framework_id, {})


def get_all_controls_flat(framework_id: str) -> list:
    """
    Return a flat list of all individual controls for a framework.
    Each item is a dict with: id, name, description, domain_name.
    Used by Module 4 (gap assessment) to iterate over every control.
    """
    # Start with the nested structure
    domains = get_controls_for_framework(framework_id)
    flat_controls = []

    for domain_key, domain_data in domains.items():
        domain_name = domain_data["domain_name"]
        for control in domain_data["controls"]:
            # Add domain context to each control for reporting
            flat_controls.append({
                "id": control["id"],
                "name": control["name"],
                "description": control["description"],
                "domain": domain_name,
            })

    return flat_controls


def get_policy_types_for_framework(framework_id: str) -> list:
    """
    Return the list of policy types available for a given framework.
    Used by Module 1 (policy generator) to populate the policy type dropdown.
    """
    return POLICY_TYPES.get(framework_id, [])


def get_domain_names(framework_id: str) -> list:
    """
    Return a list of domain names for a framework.
    Used by Module 3 (checklist) to let auditors select which domains to include.
    """
    domains = get_controls_for_framework(framework_id)
    return [data["domain_name"] for data in domains.values()]

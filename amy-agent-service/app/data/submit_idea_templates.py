"""Submit Your Idea — per-service question templates."""

from typing import Any

SUBMIT_IDEA_TEMPLATES: dict[str, dict[str, Any]] = {
    "software-app": {
        "label": "Software & App Development",
        "questions": [
            {
                "id": "platform_type",
                "text": "What type of platform do you need?",
                "type": "single_choice",
                "options": ["Web App", "Mobile App", "Both"],
                "required": True,
            },
            {
                "id": "existing_or_new",
                "text": "Is this an existing product or a new one from scratch?",
                "type": "single_choice",
                "options": ["Existing product", "New from scratch"],
                "required": True,
            },
            {
                "id": "core_features",
                "text": "What are the core features you need?",
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "integrations",
                "text": (
                    "Do you need integration with external systems or services "
                    "(payment gateway, third-party API, existing database)?"
                ),
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "target_users",
                "text": "Who are the target users of this product?",
                "type": "textarea",
                "options": [],
                "required": True,
            },
        ],
    },
    "wordpress": {
        "label": "Custom WordPress Development",
        "questions": [
            {
                "id": "site_status",
                "text": "Is this for an existing site or a new site?",
                "type": "single_choice",
                "options": ["Existing site", "New site"],
                "required": True,
            },
            {
                "id": "page_count",
                "text": "Approximate number of pages needed",
                "type": "text",
                "options": [],
                "required": True,
            },
            {
                "id": "design_status",
                "text": "Do you already have a design, or do you need one?",
                "type": "single_choice",
                "options": ["Design ready", "Need design"],
                "required": True,
            },
            {
                "id": "special_features",
                "text": (
                    "Any special features needed (e-commerce, booking system, "
                    "membership, multi-language)?"
                ),
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "hosting_domain",
                "text": (
                    "Do you already have hosting and a domain, or do you need help with this?"
                ),
                "type": "text",
                "options": [],
                "required": True,
            },
        ],
    },
    "ui-ux": {
        "label": "UI/UX Design",
        "questions": [
            {
                "id": "project_type",
                "text": "Is this a design for a website, an app, or another digital product?",
                "type": "text",
                "options": [],
                "required": True,
            },
            {
                "id": "brand_status",
                "text": "Do you already have a brand identity, or do you need one?",
                "type": "single_choice",
                "options": ["Brand ready", "Need brand identity"],
                "required": True,
            },
            {
                "id": "design_scope",
                "text": "Is this a design from scratch or a redesign of an existing product?",
                "type": "single_choice",
                "options": ["From scratch", "Redesign of existing product"],
                "required": True,
            },
            {
                "id": "screen_count",
                "text": "Approximate number of screens/pages to design",
                "type": "text",
                "options": [],
                "required": True,
            },
            {
                "id": "style_reference",
                "text": "Any websites or apps you like as a style reference?",
                "type": "textarea",
                "options": [],
                "required": False,
            },
        ],
    },
    "marketing": {
        "label": "Marketing & Strategy Consulting",
        "questions": [
            {
                "id": "primary_goal",
                "text": "What is your primary marketing goal?",
                "type": "single_choice",
                "options": [
                    "Increase sales",
                    "Build brand awareness",
                    "Launch a new product",
                    "Improve digital presence",
                ],
                "required": True,
            },
            {
                "id": "current_activity",
                "text": (
                    "Do you have current marketing activity (social media, ads), or "
                    "starting from scratch?"
                ),
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "target_audience",
                "text": "Who is your target audience?",
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "focus_platforms",
                "text": (
                    "Any specific platforms to focus on (Instagram, LinkedIn, Google Ads...)?"
                ),
                "type": "text",
                "options": [],
                "required": False,
            },
        ],
    },
    "cybersecurity": {
        "label": "Cybersecurity",
        "questions": [
            {
                "id": "protection_type",
                "text": "What type of cybersecurity help do you need?",
                "type": "single_choice",
                "options": [
                    "Security assessment/audit",
                    "Website or app protection",
                    "Incident response",
                    "General data protection",
                ],
                "required": True,
            },
            {
                "id": "past_incident",
                "text": (
                    "Have you experienced a security issue (breach, data leak) "
                    "with this project before?"
                ),
                "type": "text",
                "options": [],
                "required": True,
            },
            {
                "id": "system_nature",
                "text": (
                    "What is the nature of the system to be protected "
                    "(website, app, server, internal network)?"
                ),
                "type": "text",
                "options": [],
                "required": True,
            },
            {
                "id": "compliance_requirements",
                "text": (
                    "Any specific compliance requirements we must follow (GDPR, etc.)?"
                ),
                "type": "text",
                "options": [],
                "required": False,
            },
        ],
    },
    "ai-solutions": {
        "label": "AI Solutions",
        "questions": [
            {
                "id": "solution_type",
                "text": "What type of AI solution are you looking for?",
                "type": "single_choice",
                "options": [
                    "Task automation",
                    "Chatbot",
                    "Data analysis",
                    "Recommendation system",
                    "Other custom solution",
                ],
                "required": True,
            },
            {
                "id": "existing_systems",
                "text": (
                    "Do you have existing data or systems this solution needs to integrate with?"
                ),
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "core_problem",
                "text": "What specific problem or task do you want AI to solve?",
                "type": "textarea",
                "options": [],
                "required": True,
            },
            {
                "id": "expected_scale",
                "text": "Approximate expected data volume or number of users",
                "type": "text",
                "options": [],
                "required": False,
            },
        ],
    },
}

"""SARA Accessibility Tutor: uses the same guarded assessment runtime."""
import os

from SARA_AI_Product_Manager_Adaptive_Tutor_UNIFIED import (
    AnswerSealer, RoadVerifierClient, SaraQuestionClient, Store, TutorService, create_app,
)

ACCESSIBILITY_COMPETENCIES = [
    'disability_and_assistive_technology', 'universal_design', 'wcag',
    'section_508', 'accessible_documents', 'testing_and_remediation',
    'procurement_and_governance', 'workplace_judgment',
]

EXAM_REQUIREMENTS = {
    'curriculum': 'CPACC, Section 508, WCAG, accessible documents, practical testing and remediation',
    'style': ['scenario-based best answer', 'first action under incomplete evidence',
              'negative wording', 'plausible distractors', 'unpredictable domain shifts',
              'workplace curveballs'],
    'knowledge_rules': ['distinguish CPACC outline references from newer WCAG versions',
                        'distinguish Revised Section 508 incorporation from current WCAG',
                        'do not claim access to proprietary Pearson VUE item-selection algorithms'],
    'source_rule': 'Provide current verifiable citations in evidence_notes; ROAD must reject unsupported standards claims.',
}


class AccessibilityQuestionClient(SaraQuestionClient):
    def __init__(self, url, token, timeout=20.0, transport=None):
        super().__init__(url, token, timeout, transport,
                         task='generate_accessibility_assessment_item',
                         curriculum_requirements=EXAM_REQUIREMENTS)


def build_accessibility_service():
    required = ('SARA_GENERATOR_URL', 'SARA_GENERATOR_TOKEN', 'ROAD_VERIFIER_URL',
                'ROAD_VERIFIER_TOKEN', 'SARA_TUTOR_HMAC_SECRET')
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError('Missing required configuration: ' + ', '.join(missing))
    return TutorService(
        Store(os.getenv('SARA_ACCESSIBILITY_DB_PATH', '/data/sara_accessibility_tutor.db')),
        AccessibilityQuestionClient(os.environ['SARA_GENERATOR_URL'], os.environ['SARA_GENERATOR_TOKEN']),
        RoadVerifierClient(os.environ['ROAD_VERIFIER_URL'], os.environ['ROAD_VERIFIER_TOKEN'],
                           task='verify_accessibility_assessment_item'),
        AnswerSealer(os.environ['SARA_TUTOR_HMAC_SECRET'].encode()),
        competencies=ACCESSIBILITY_COMPETENCIES,
    )


app = create_app(service_builder=build_accessibility_service)
app.title = 'SARA Accessibility Tutor'

import pathlib
import tempfile
import unittest
import sqlite3
import concurrent.futures

from fastapi.testclient import TestClient

import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import SARA_AI_Product_Manager_Adaptive_Tutor_UNIFIED as tutor

sys.modules['SARA_AI_Product_Manager_Adaptive_Tutor_UNIFIED_GLOBAL_NOVELTY'] = tutor


class MadhouseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = tutor.Store(str(pathlib.Path(self.tmp.name) / 'tutor.db'))
        self.sealer = tutor.AnswerSealer(b'x' * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def test_repeat_wrong_submission_scores_once(self):
        qid = 'q1'
        self.store.save_question(dict(id=qid, learner_id='alice', competency='rag', difficulty=1,
            prompt='Which evidence matters?', choices=['a','b','c','d'],
            answer_commitment=self.sealer.seal(qid, 2), explanation='Reason', reasoning='evaluate', fingerprint='fp1'))
        service = tutor.TutorService(self.store, None, None, self.sealer)
        first = service.answer('alice', qid, 0)
        second = service.answer('alice', qid, 0)
        correct = service.answer('alice', qid, 2)
        self.assertEqual(first['mastery'], second['mastery'])
        self.assertEqual(second['mastery'], correct['mastery'])
        self.assertEqual(self.store.get_mastery('alice')['rag'].attempts, 1)

    def test_learner_url_cannot_access_without_subject_token(self):
        service = tutor.TutorService(self.store, None, None, self.sealer)
        client = TestClient(tutor.create_app(service))
        self.assertEqual(client.get('/v1/session/alice/mastery').status_code, 401)
        token = tutor.issue_learner_token('alice', b'x' * 32)
        self.assertEqual(client.get('/v1/session/bob/mastery', headers={'Authorization': 'Bearer '+token}).status_code, 403)
        self.assertEqual(client.get('/v1/session/alice/mastery', headers={'Authorization': 'Bearer '+token}).status_code, 200)

    def test_objective_can_recur_with_distinct_reasoning(self):
        base = dict(prompt='Select a grounded answer when retrieval conflicts with metrics.',
            choices=['one','two','three','four'],correct_index=0,learning_objective_id='evaluate retrieval',
            reasoning_signature='compare provenance with time scope',
            correct_answer_signature='prefer sourced current evidence',
            distractor_signatures=['old metrics','unsupported summary','irrelevant dashboard'],
            scenario_signature='retrieval conflict in medical product')
        changed = dict(base, prompt='Plan evaluation of RAG freshness in a financial release.',
            reasoning_signature='select longitudinal evaluation metric',
            correct_answer_signature='run time split evaluation',
            distractor_signatures=['single anecdote','uncontrolled benchmark','metric leakage'],
            scenario_signature='financial release longitudinal monitoring')
        self.assertTrue(self.store.claim_novelty(base, .72))
        self.assertTrue(self.store.claim_novelty(changed, .72))
        self.assertFalse(self.store.claim_novelty(changed, .72))

    def test_choice_position_balances(self):
        service = tutor.TutorService(self.store, None, None, self.sealer)
        positions = [service.choose_answer_position() for _ in range(12)]
        counts = [positions.count(i) for i in range(4)]
        self.assertLessEqual(max(counts)-min(counts), 1)

    def test_accessibility_domain_and_exam_constraints_are_sent_to_generator(self):
        import asyncio
        import httpx
        import accessibility_tutor as access
        observed = {}
        def handler(request):
            observed.update(__import__('json').loads(request.content))
            return httpx.Response(200, json={})
        client = access.AccessibilityQuestionClient('https://example.test', 'token', transport=httpx.MockTransport(handler))
        with self.assertRaises(tutor.ProviderContractError):
            asyncio.run(client.generate_question('accessible_documents', 4, {}))
        self.assertEqual(observed['task'], 'generate_accessibility_assessment_item')
        self.assertIn('WCAG', str(observed['requirements']))
        self.assertIn('negative wording', str(observed['requirements']))

    def test_concurrent_wrong_answers_are_one_scored_attempt(self):
        qid = 'race'
        self.store.save_question(dict(id=qid, learner_id='alice', competency='rag', difficulty=1,
            prompt='Choose evidence', choices=['a','b','c','d'],
            answer_commitment=self.sealer.seal(qid, 2), explanation='Reason', reasoning='evaluate', fingerprint='race'))
        service = tutor.TutorService(self.store, None, None, self.sealer)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: service.answer('alice', qid, 0), range(12)))
        self.assertEqual(self.store.get_mastery('alice')['rag'].attempts, 1)

    def test_expired_and_tampered_tokens_rejected(self):
        import time
        token = tutor.issue_learner_token('alice', b'x'*32)
        with self.assertRaises(Exception):
            tutor.require_learner('alice', 'Bearer ' + token[:-1] + ('a' if token[-1] != 'a' else 'b'), b'x'*32)
        original = tutor.time.time
        try:
            tutor.time.time = lambda: original() + 3601
            with self.assertRaises(Exception):
                tutor.require_learner('alice', 'Bearer ' + token, b'x'*32)
        finally:
            tutor.time.time = original

    def test_existing_database_migrates_unique_objective_constraint(self):
        path = pathlib.Path(self.tmp.name) / 'old.db'
        connection = sqlite3.connect(path)
        try:
            connection.execute('''CREATE TABLE novelty_ledger(
                fingerprint TEXT PRIMARY KEY, prompt TEXT NOT NULL,
                learning_objective_id TEXT NOT NULL UNIQUE,
                reasoning_signature TEXT NOT NULL UNIQUE,
                correct_answer_signature TEXT NOT NULL UNIQUE,
                distractor_key TEXT NOT NULL UNIQUE,
                distractor_signatures_json TEXT NOT NULL,
                scenario_signature TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            connection.commit()
        finally:
            connection.close()
        migrated = tutor.Store(str(path))
        self.assertIsNotNone(migrated)
        connection = sqlite3.connect(path)
        try:
            indexes = connection.execute('PRAGMA index_list(novelty_ledger)').fetchall()
            self.assertFalse(any([c[2] for c in connection.execute('PRAGMA index_info('+idx[1]+')')] == ['learning_objective_id']
                                 and idx[2] for idx in indexes))
        finally:
            connection.close()

    def test_accessibility_question_is_verified_then_served_without_key(self):
        import asyncio
        import accessibility_tutor as access
        class Generator:
            async def generate_question(self, competency, difficulty, learner_context):
                return dict(prompt='A document has a scanned image of its entire text. What should the team do first?',
                    choices=['Check text extraction and reading order', 'Increase the font size',
                             'Change the page color', 'Add a decorative title'], correct_index=2,
                    explanation='Check whether meaningful text is available.', competency=competency,
                    difficulty=difficulty, reasoning_archetype='evaluate first action', evidence_notes='document testing',
                    learning_objective_id='document text availability', reasoning_signature='check scanned content access',
                    correct_answer_signature='assess available text and reading order',
                    distractor_signatures=['font only', 'color only', 'decoration only'],
                    scenario_signature='scanned document triage')
        class Road:
            async def verify_question(self, question):
                return {'status': 'PASS', 'verified': True}
        service = tutor.TutorService(self.store, Generator(), Road(), self.sealer,
                                     competencies=access.ACCESSIBILITY_COMPETENCIES)
        item = asyncio.run(service.next_question('alice'))
        self.assertEqual(set(item), {'question_id','prompt','choices','competency','difficulty'})
        self.assertIn(item['competency'], access.ACCESSIBILITY_COMPETENCIES)
        correct_choice = 'Change the page color'
        result = service.answer('alice', item['question_id'], item['choices'].index(correct_choice))
        self.assertTrue(result['correct'])


if __name__ == '__main__': unittest.main()

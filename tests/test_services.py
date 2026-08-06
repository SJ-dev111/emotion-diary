"""활용 규칙 엔진(conjugator)·감정 인식기(emotion_detector) 테스트."""
import unittest

from app.services import conjugator as cj
from app.services import emotion_detector as det
from app.db import database
from app.db.emotion_repo import EmotionRepo


class ConjugatorStemTest(unittest.TestCase):
    def test_hada(self):
        self.assertEqual(cj.generate_stems("서운하다"), ["서운"])
        self.assertEqual(cj.generate_stems("행복하다"), ["행복"])

    def test_doeda(self):
        self.assertEqual(cj.generate_stems("걱정되다"), ["걱정"])

    def test_nada_with_particle(self):
        self.assertEqual(cj.generate_stems("화나다"), ["화나", "화가 나"])
        self.assertEqual(cj.generate_stems("신나다"), ["신나", "신이 나"])

    def test_b_irregular(self):
        self.assertEqual(cj.generate_stems("두렵다"), ["두렵", "두려우"])
        self.assertEqual(cj.generate_stems("무섭다"), ["무섭", "무서우"])

    def test_eu_drop(self):
        self.assertEqual(cj.generate_stems("슬프다"), ["슬프", "슬퍼"])
        self.assertEqual(cj.generate_stems("아프다"), ["아프", "아파"])  # 모음조화

    def test_i_contract(self):
        self.assertEqual(cj.generate_stems("지치다"), ["지치", "지쳐"])

    def test_plain_vowel_no_extra(self):
        self.assertEqual(cj.generate_stems("설레다"), ["설레"])

    def test_non_verb_passthrough(self):
        self.assertEqual(cj.generate_stems("우울"), ["우울"])


class ConjugatorFormsTest(unittest.TestCase):
    def _forms(self, word):
        return dict(cj.forms(word))

    def test_hada_full_seven(self):
        f = self._forms("행복하다")
        self.assertEqual(f, {
            "기본형": "행복하다", "과거형": "행복했다", "관형형": "행복한",
            "연결형": "행복해서", "명사형": "행복함", "의문형": "행복할까",
            "변화형": "행복해졌다"})

    def test_b_irregular(self):
        f = self._forms("무섭다")
        self.assertEqual(f["과거형"], "무서웠다")
        self.assertEqual(f["관형형"], "무서운")
        self.assertEqual(f["연결형"], "무서워서")
        self.assertEqual(f["명사형"], "무서움")
        self.assertEqual(f["의문형"], "무서울까")
        self.assertEqual(f["변화형"], "무서워졌다")

    def test_eu_drop(self):
        f = self._forms("슬프다")
        self.assertEqual(f["과거형"], "슬펐다")
        self.assertEqual(f["관형형"], "슬픈")
        self.assertEqual(f["명사형"], "슬픔")
        self.assertEqual(f["의문형"], "슬플까")

    def test_batchim_regular(self):
        f = self._forms("열받다")
        self.assertEqual(f["과거형"], "열받았다")
        self.assertEqual(f["관형형"], "열받은")
        self.assertEqual(f["연결형"], "열받아서")
        self.assertEqual(f["의문형"], "열받을까")

    def test_nada_skips_change_form(self):
        f = self._forms("화나다")
        self.assertEqual(f["과거형"], "화났다")
        self.assertEqual(f["관형형"], "화난")
        self.assertNotIn("변화형", f)

    def test_doeda(self):
        f = self._forms("걱정되다")
        self.assertEqual(f["과거형"], "걱정됐다")
        self.assertEqual(f["연결형"], "걱정돼서")
        self.assertNotIn("변화형", f)


class DetectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = database.connect(":memory:")
        database.init_db(conn)
        cls.vocab = EmotionRepo(conn).all_for_matching()
        conn.close()

    def _words(self, text):
        return [m.word for m in det.detect(text, self.vocab)]

    def test_basic_match(self):
        self.assertEqual(self._words("오늘 정말 행복했다"), ["행복하다"])

    def test_jamo_noun_form(self):
        self.assertIn("슬프다", self._words("슬픔이 몰려왔다"))

    def test_jamo_b_irregular(self):
        self.assertIn("서럽다", self._words("서러운 하루였다"))
        self.assertIn("무섭다", self._words("정말 무서웠다"))

    def test_word_start_boundary(self):
        self.assertEqual(self._words("영화나 봤다"), [])       # 화나다 오인식 방지
        self.assertEqual(self._words("충분하다고 했다"), [])   # 분하다 오인식 방지

    def test_spaced_stem(self):
        self.assertIn("화나다", self._words("정말 화가 났다"))

    def test_negation_after(self):
        self.assertEqual(self._words("행복하지 않았다"), [])
        self.assertEqual(self._words("행복하지않았다"), [])
        self.assertEqual(self._words("두렵지 못했다"), [])

    def test_negation_before(self):
        self.assertEqual(self._words("안 행복했다"), [])
        self.assertEqual(self._words("못 즐거웠다"), [])

    def test_negation_not_confused_with_jiman(self):
        # "~지만"은 부정이 아니다
        self.assertIn("슬프다", self._words("슬프지만 웃었다"))

    def test_highlight_span_covers_eojeol(self):
        text = "오늘 무서웠다"
        m = det.detect(text, self.vocab)[0]
        self.assertEqual(text[m.start:m.end], "무서웠다")

    def test_same_word_multiple_stems_dedup(self):
        # 놀랍다 어간(놀랍/놀라우/놀라)이 "놀라운"에 중복 매칭되지 않아야 함
        matches = [m for m in det.detect("놀라운 일이었다", self.vocab)
                   if m.word == "놀랍다"]
        self.assertEqual(len(matches), 1)

    def test_count_tags(self):
        tags = det.count_tags("불안하고 초조했다. 계속 불안했다.", self.vocab)
        self.assertIn(("불안하다", "불안", 2), tags)
        self.assertIn(("초조하다", "불안", 1), tags)

    def test_empty_text(self):
        self.assertEqual(det.detect("", self.vocab), [])

    # ── match_words (자동완성 추천·검색 공용) ─────────────────

    def test_match_words_partial_stem(self):
        self.assertIn("서럽다", det.match_words("서러", self.vocab))

    def test_match_words_conjugated_form(self):
        self.assertIn("서럽다", det.match_words("서러웠다", self.vocab))
        self.assertIn("무섭다", det.match_words("무서웠", self.vocab))

    def test_match_words_base_prefix(self):
        self.assertIn("행복하다", det.match_words("행복", self.vocab))

    def test_match_words_no_match(self):
        self.assertEqual(det.match_words("김치", self.vocab), [])
        self.assertEqual(det.match_words("", self.vocab), [])

    # ── suggest_from_lexicon (단어집에 없는 감정 표현 제안) ────

    def test_suggest_from_lexicon_conjugated(self):
        self.assertEqual(det.suggest_from_lexicon("허탈했다"),
                         ("허탈하다", "슬픔"))
        self.assertEqual(det.suggest_from_lexicon("부러웠다")[0], "부럽다")

    def test_suggest_from_lexicon_non_emotion(self):
        self.assertIsNone(det.suggest_from_lexicon("김치찌개"))
        self.assertIsNone(det.suggest_from_lexicon("가"))


if __name__ == "__main__":
    unittest.main()

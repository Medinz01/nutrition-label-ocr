from semantic_parser import match_nutrient,extract_number

class TestMatchNutrient:
    def test_match_nutrient(self):
        res = match_nutrient("protein 5g")
        assert res == "protein_g"

    def test_noise_variants(self):
        res = match_nutrient("orotein 5g")
        assert res == "protein_g"

    def test_returns_none_for_unknown(self):
        result = match_nutrient("random text")
        assert result is None

class TestExtractNumber:
    def test_ocr_substitution_I_to_1(self):
        res = extract_number("I5g")
        assert res == 15.0

    def test_ocr_substitution_O_to_0(self):
        result = extract_number("O5g")
        assert result == 5.0  

    def test_comma_as_decimal(self):
        result = extract_number("25,5g")
        assert result == 25.5 

    def test_returns_none_when_no_number(self):
        result = extract_number("no number here")
        assert result is None

    def test_basic_number(self):
        result = extract_number("25g")
        assert result == 25.0
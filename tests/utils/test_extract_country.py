from src.utils import extract_country


class TestExtractCountry:
    def test_standard_format(self):
        wikitext = ";country your from:Rwanda\n"
        assert extract_country(wikitext) == "Rwanda"

    def test_space_before_value(self):
        wikitext = "; country your from: Rwanda\n"
        assert extract_country(wikitext) == "Rwanda"

    def test_no_space_after_semicolon(self):
        wikitext = ";country your from: Germany\n"
        assert extract_country(wikitext) == "Germany"

    def test_case_insensitive(self):
        wikitext = "; Country Your From: France\n"
        assert extract_country(wikitext) == "France"

    def test_multiline_takes_first_line(self):
        wikitext = "; country your from:Kenya\n== Explain your plan ==\nSome text"
        assert extract_country(wikitext) == "Kenya"

    def test_no_country_field(self):
        wikitext = "== Your contact information ==\n;your username: [[User]]\n"
        assert extract_country(wikitext) == ""

    def test_empty_string(self):
        assert extract_country("") == ""

    def test_full_application_example(self):
        wikitext = (
            "<!-- Please contact asaf@wikimedia.org if you have questions.-->\n"
            "\n"
            "== Your contact information ==\n"
            ";your username: [[username]]\n"
            ";a contact e-mail: username@gmail.com\n"
            "; country your from:Rwanda\n"
            "\n"
            "== Explain your plan ==\n"
            "I plan to use the laptop for...\n"
        )
        assert extract_country(wikitext) == "Rwanda"

    def test_country_with_trailing_whitespace(self):
        wikitext = "; country your from:  India  \n"
        assert extract_country(wikitext) == "India"

    def test_country_with_carriage_return(self):
        wikitext = "; country your from:Brazil\r\n"
        assert extract_country(wikitext) == "Brazil"

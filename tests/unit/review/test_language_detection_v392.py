"""v3.9.2 F9: stdlib-only language detection must name French, German,
Spanish, Italian, Portuguese, Romanian and English correctly and must never
report a wrong named language for text it cannot place."""

import pytest

from qai_consultant.common.text_checks import detect_language, has_qa_signal
from qai_consultant.core.review_core import review_document

SAMPLES = {
    "fr": (
        "Le plan de test décrit la stratégie de vérification de l'application de paiement. "
        "Les tests fonctionnels sont exécutés par l'équipe dans l'environnement de recette, "
        "et les anomalies sont consignées dans l'outil de suivi. Les critères d'entrée sont "
        "que toutes les exigences soient implémentées, et les critères de sortie sont que "
        "tous les tests critiques passent avec succès. Les risques principaux concernent "
        "l'intégration avec le prestataire de paiement et le volume de transactions."
    ),
    "de": (
        "Der Testplan beschreibt den Umfang und die Strategie für das Testen der Anwendung. "
        "Die Tests werden von dem Team in der Staging Umgebung ausgeführt und die Fehler "
        "werden in einem System erfasst, das von allen Beteiligten genutzt wird. Die "
        "Eingangskriterien sind erfüllt, wenn alle Anforderungen umgesetzt wurden, und die "
        "Ausgangskriterien verlangen, dass alle kritischen Tests erfolgreich sind."
    ),
    "es": (
        "El plan de pruebas describe el alcance y la estrategia de verificación de la "
        "aplicación de pagos. Las pruebas funcionales serán ejecutadas por el equipo en el "
        "entorno de preproducción y los defectos se registrarán en la herramienta de "
        "seguimiento. Los criterios de entrada son que todos los requisitos estén "
        "implementados, y los criterios de salida son que las pruebas críticas pasen."
    ),
    "it": (
        "Il piano di test descrive l'ambito e la strategia di verifica dell'applicazione di "
        "pagamento. I test funzionali sono eseguiti dal team nell'ambiente di collaudo e i "
        "difetti sono registrati nello strumento di tracciamento. I criteri di ingresso "
        "sono che tutti i requisiti siano implementati, e i criteri di uscita sono che "
        "tutti i test critici vengano superati con successo."
    ),
    "pt": (
        "O plano de testes descreve o escopo e a estratégia de verificação da aplicação de "
        "pagamentos. Os testes funcionais serão executados pela equipe no ambiente de "
        "homologação e os defeitos são registrados na ferramenta de acompanhamento. Os "
        "critérios de entrada são que todos os requisitos estejam implementados, e os "
        "critérios de saída são que os testes críticos passem com sucesso."
    ),
    "ro": (
        "Planul de testare descrie abordarea pentru modulul de plată al aplicației. "
        "Echipa de testare va executa testele funcționale în mediul de staging, iar "
        "defectele sunt raportate în sistemul de urmărire. Criteriile de intrare sunt ca "
        "toate cerințele să fie implementate, iar criteriile de ieșire sunt ca toate "
        "testele critice să treacă cu succes."
    ),
    "en": (
        "This test plan describes the scope and the approach for verifying the payment "
        "module. The functional tests will be executed by the team in the staging "
        "environment, and all defects are logged in the tracking tool. The entry criteria "
        "are that every requirement has been implemented, and the exit criteria are that "
        "all critical tests pass."
    ),
}


@pytest.mark.parametrize("code", sorted(SAMPLES))
def test_language_is_identified(code):
    d = detect_language(SAMPLES[code])
    assert d["language"] == code
    assert d["reliable"] is (code == "en")
    assert bool(d["warning"]) is (code != "en")


def test_french_is_not_reported_as_romanian():
    assert detect_language(SAMPLES["fr"])["language"] != "ro"
    assert "French" in detect_language(SAMPLES["fr"])["warning"]


def test_unplaceable_language_is_other_not_a_wrong_name():
    finnish = (
        "Testaussuunnitelma kuvaa sovelluksen laajuuden ja strategian. Toiminnalliset "
        "testit suoritetaan tiimin toimesta testiympäristössä ja virheet kirjataan "
        "seurantajärjestelmään, jota kaikki osapuolet käyttävät. Tuloehdot täyttyvät, kun "
        "kaikki vaatimukset on toteutettu, ja poistumisehdot edellyttävät kriittisten "
        "testien läpäisyä."
    )
    d = detect_language(finnish)
    assert d["language"] == "other" and d["reliable"] is False


def test_short_text_is_unknown():
    assert detect_language("Testplan pour login")["language"] == "unknown"


def test_review_reports_french_and_keeps_unreliable_score():
    r = review_document(SAMPLES["fr"] + " Test plan test cases scope risk.", doc_type="test_plan")
    assert r.language == "fr"
    assert r.score_reliable is False and r.language_warning


def test_has_qa_signal():
    assert has_qa_signal("# Test Plan")
    assert has_qa_signal("Test 1: check the thing works")
    assert has_qa_signal("We will do thorough testing.")
    assert not has_qa_signal("Boil the pasta for ten minutes and serve.")

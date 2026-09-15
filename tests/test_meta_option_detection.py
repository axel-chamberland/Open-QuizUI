import pytest

from backend.quiz_function import refers_to_other_options


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # English — common
        ("All of the above", True),
        ("All of the following", True),
        ("None of the above", True),
        ("Both A and B", True),
        ("A and B", True),
        ("A, B, and C", True),
        ("A–C", True),
        ("A through D", True),
        ("Options A and B", True),
        ("Choice C", True),
        ("Answer B", True),
        ("The answer above", True),
        ("The option above", True),
        ("The previous answer", True),
        ("The previous option", True),
        ("The choices above", True),
        ("The answers listed above", True),
        ("The statements above", True),
        ("The statements in A–C", True),
        ("A and B are correct", True),
        ("A–D are correct", True),
        # French — common
        ("Toutes les réponses ci-dessus", True),
        ("Toutes les propositions ci-dessus", True),
        ("Toutes les réponses suivantes", True),
        ("A et B", True),
        ("A, B et C", True),
        ("A à D", True),
        ("Les options A et B", True),
        ("La réponse B", True),
        ("Le choix C", True),
        ("La réponse ci-dessus", True),
        ("La proposition ci-dessus", True),
        ("La réponse précédente", True),
        ("La proposition précédente", True),
        ("Les choix ci-dessus", True),
        ("Les réponses précédentes", True),
        ("Les affirmations ci-dessus", True),
        ("Les propositions A à C", True),
        ("A et B sont correctes", True),
        ("A–D sont correctes", True),
        # Normal short answers — should NOT match
        ("ATP", False),
        ("DNA", False),
        ("RNA polymerase", False),
        ("Mitochondria", False),
        ("Cell membrane", False),
        ("Protein synthesis", False),
        ("3′ to 5′", False),
        ("37 °C", False),
        ("Two hours", False),
        ("In the nucleus", False),
        ("Paroi cellulaire", False),
        ("Membrane plasmique", False),
        ("Synthèse des protéines", False),
        ("Dans le cytoplasme", False),
        ("À 37 °C", False),
        # Normal longer answers — should NOT match
        ("The enzyme binds to the substrate.", False),
        ("DNA polymerase adds nucleotides to the growing strand.", False),
        ("The mutation changes one nucleotide.", False),
        ("The protein is located in the nucleus.", False),
        ("This process requires ATP.", False),
        ("La protéine se lie à l'ADN.", False),
        ("L'ARN polymérase synthétise l'ARN.", False),
        ("Cette mutation modifie la séquence codante.", False),
        ("La réaction nécessite de l'ATP.", False),
    ],
)
def test_choice_reference_detection(text, expected):
    assert (
        refers_to_other_options(
            text,
            r"\p{L}",
            [],
        )
        is expected
    )

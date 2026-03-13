"""
Mock California Civil Code legal library with keyword-based retrieval.
Each entry maps a statute to its text and a set of retrieval keywords.
"""

from dataclasses import dataclass


@dataclass
class Statute:
    citation: str
    title: str
    text: str
    keywords: list[str]

    def __str__(self) -> str:
        return f"{self.citation} — {self.title}: {self.text}"


LIBRARY: list[Statute] = [
    Statute(
        citation="Cal. Civ. Code § 1714",
        title="General Negligence",
        text=(
            "Everyone is responsible, not only for the result of their willful acts, "
            "but also for an injury occasioned to another by their want of ordinary care "
            "or skill in the management of their property or person."
        ),
        keywords=["negligence", "injury", "care", "accident", "harm", "damage", "hurt",
                  "careless", "reckless", "duty", "slip", "fall", "crash", "collision"],
    ),
    Statute(
        citation="Cal. Civ. Code § 3294",
        title="Punitive Damages",
        text=(
            "In an action for breach of an obligation not arising from contract, where "
            "the defendant has been guilty of oppression, fraud, or malice, the plaintiff "
            "may recover damages for the sake of example and by way of punishing the defendant."
        ),
        keywords=["punitive", "malice", "fraud", "oppression", "willful", "intentional",
                  "egregious", "bad faith", "deliberate", "exemplary"],
    ),
    Statute(
        citation="Cal. Civ. Code § 1572",
        title="Actual Fraud",
        text=(
            "Actual fraud consists in the suggestion as a fact of that which is not true "
            "by one who does not believe it to be true; the suppression of that which is "
            "true by one who is legally or morally bound to disclose it; or a promise made "
            "without any intention of performing it."
        ),
        keywords=["fraud", "misrepresentation", "false", "lie", "deceive", "deception",
                  "mislead", "concealment", "omission", "promise", "false statement"],
    ),
    Statute(
        citation="Cal. Civ. Code § 3333",
        title="Tort Damages — Out-of-Pocket Loss",
        text=(
            "For the breach of an obligation not arising from contract, the measure of "
            "damages is the amount which will compensate for all the detriment proximately "
            "caused thereby, whether it could have been anticipated or not."
        ),
        keywords=["damages", "compensation", "loss", "detriment", "medical", "expenses",
                  "lost wages", "pain", "suffering", "economic", "tort"],
    ),
    Statute(
        citation="Cal. Civ. Code § 1750",
        title="Consumer Legal Remedies Act (CLRA)",
        text=(
            "The CLRA prohibits unfair or deceptive acts or practices undertaken by any "
            "person in a transaction intended to result in the sale or lease of goods or "
            "services to any consumer."
        ),
        keywords=["consumer", "product", "sale", "goods", "services", "deceptive",
                  "unfair", "defective", "warranty", "purchase", "merchant", "seller"],
    ),
    Statute(
        citation="Cal. Civ. Code § 1927",
        title="Implied Warranty of Habitability",
        text=(
            "An agreement to let upon hire a thing for use by the hirer implies on the "
            "part of the lessor a warranty that such thing is fit for the purpose for which "
            "it is hired and that he will put it in as good a condition as it ought to be "
            "at the time of the hiring."
        ),
        keywords=["landlord", "tenant", "rent", "lease", "habitability", "property",
                  "apartment", "housing", "repairs", "mold", "unsafe", "unit", "dwelling"],
    ),
    Statute(
        citation="Cal. Civ. Code § 51",
        title="Unruh Civil Rights Act",
        text=(
            "All persons within the jurisdiction of this state are free and equal, and no "
            "matter what their sex, race, color, religion, ancestry, national origin, "
            "disability, medical condition, genetic information, marital status, sexual "
            "orientation, citizenship, primary language, or immigration status are entitled "
            "to the full and equal accommodations, advantages, facilities, privileges, or "
            "services in all business establishments of every kind whatsoever."
        ),
        keywords=["discrimination", "race", "gender", "disability", "civil rights",
                  "business", "equal", "access", "refused", "harassment", "bias"],
    ),
    Statute(
        citation="Cal. Civ. Code § 3479",
        title="Nuisance",
        text=(
            "Anything which is injurious to health, including but not limited to the "
            "illegal sale of controlled substances, or is indecent or offensive to the "
            "senses, or an obstruction to the free use of property, so as to interfere "
            "with the comfortable enjoyment of life or property, is a nuisance."
        ),
        keywords=["nuisance", "noise", "pollution", "neighbor", "obstruction", "health",
                  "offensive", "property use", "interference", "environment", "toxic"],
    ),
    Statute(
        citation="Cal. Civ. Code § 2338",
        title="Principal Liability for Agent",
        text=(
            "Unless required by or under the authority of law to employ that particular "
            "agent, a principal is responsible to third persons for the negligence of his "
            "agent in the transaction of the business of the agency, including wrongful "
            "acts committed by such agent in and as part of the transaction of such business."
        ),
        keywords=["employer", "employee", "agent", "principal", "respondeat superior",
                  "vicarious", "company", "business", "staff", "worker", "contractor"],
    ),
    Statute(
        citation="Cal. Civ. Code § 1668",
        title="Contracts Exempting Negligence — Void",
        text=(
            "All contracts which have for their object, directly or indirectly, to exempt "
            "anyone from responsibility for their own fraud, or willful injury to the person "
            "or property of another, or violation of law, whether willful or negligent, are "
            "against the policy of the law."
        ),
        keywords=["waiver", "release", "contract", "liability clause", "indemnity",
                  "exemption", "disclaimer", "signed", "agreement", "terms"],
    ),
]


def retrieve_statutes(case_facts: str, max_results: int = 4) -> list[Statute]:
    """Return the top `max_results` statutes most relevant to the case facts."""
    facts_lower = case_facts.lower()
    scored: list[tuple[int, Statute]] = []

    for statute in LIBRARY:
        score = sum(1 for kw in statute.keywords if kw in facts_lower)
        scored.append((score, statute))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Always include at least the top result even if score is 0
    top = [s for score, s in scored if score > 0]
    if not top:
        top = [scored[0][1]]

    return top[:max_results]


def format_statutes(statutes: list[Statute]) -> str:
    """Format a list of statutes as a numbered reference block."""
    lines = []
    for i, s in enumerate(statutes, 1):
        lines.append(f"{i}. {s}")
    return "\n".join(lines)

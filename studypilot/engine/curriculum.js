// Programme de première générale 2026-2027 — données de départ.
// Statut de vérification : "maths" doit être confronté au BO n°14 du 2 avril 2026
// (MENE2602917A, nouveau programme de spécialité mathématiques, rentrée 2026) :
// le site du ministère n'a pas pu être lu automatiquement. Tout est modifiable
// dans l'app (page Programme) : ordre du professeur, ajout/suppression de notions.
export const STATUTS = ["non_etudiee", "decouverte", "en_cours", "etudiee", "a_consolider", "maitrisee"];
export const STATUT_LABEL = {
  non_etudiee: "Non étudiée", decouverte: "Découverte en avance", en_cours: "En cours au lycée",
  etudiee: "Étudiée", a_consolider: "À consolider", maitrisee: "Maîtrisée",
};

// Coefficients du bac (réforme en vigueur) — utilisés pour la simulation.
// prio : poids pédagogique pour le planning (BUT GEII → maths, PC, SI).
export const MATIERES = [
  { id: "maths", nom: "Mathématiques", prio: 3, verif: "à vérifier (programme modifié rentrée 2026)" },
  { id: "pc", nom: "Physique-chimie", prio: 3, verif: "programme 2019 en vigueur" },
  { id: "si", nom: "Sciences de l'ingénieur", prio: 3, verif: "programme 2019 en vigueur" },
  { id: "fr", nom: "Français (bac de français)", prio: 2.5, verif: "programme 2019 en vigueur" },
  { id: "hg", nom: "Histoire-géographie", prio: 1.5, verif: "programme 2019 en vigueur" },
  { id: "ang", nom: "Anglais (LVA)", prio: 1, verif: "programme 2019 en vigueur" },
  { id: "lvb", nom: "LVB", prio: 1, verif: "" },
  { id: "es", nom: "Enseignement scientifique", prio: 1.5, verif: "programme 2019 en vigueur" },
  { id: "emc", nom: "EMC", prio: 0.5, verif: "" },
  { id: "eps", nom: "EPS", prio: 0.3, verif: "" },
];

// [id, titre, prérequis ids, utilité concrète]
const T = (theme, chapitres) => ({ theme, chapitres });
const C = (id, titre, notions) => ({ id, titre, notions: notions.map(([nid, t, pre = [], util = ""]) => ({ id: nid, titre: t, prerequis: pre, utilite: util })) });

export const PROGRAMME = {
  maths: [
    T("Algèbre", [
      C("m-suites", "Suites numériques", [
        ["m-suites-def", "Modes de génération d'une suite (explicite, récurrence)", [], "Modéliser une batterie qui perd x % par cycle"],
        ["m-suites-arith", "Suites arithmétiques : terme général, somme", ["m-suites-def"], "Amortissement linéaire, compteur"],
        ["m-suites-geo", "Suites géométriques : terme général, somme", ["m-suites-def"], "Décharge d'un condensateur échantillonnée"],
        ["m-suites-var", "Sens de variation, notion de limite (intuitive)", ["m-suites-arith", "m-suites-geo"], ""],
        ["m-suites-algo", "Algorithmes et suites (Python)", ["m-suites-def"], "Boucles sur ESP32/MicroPython"],
      ]),
      C("m-second", "Équations, fonctions polynômes du second degré", [
        ["m-2d-forme", "Forme canonique, forme factorisée", [], "Trajectoire, optimisation"],
        ["m-2d-delta", "Discriminant, racines", ["m-2d-forme"], "Résoudre une équation de puissance P = RI²"],
        ["m-2d-signe", "Signe d'un trinôme, inéquations", ["m-2d-delta"], ""],
      ]),
    ]),
    T("Analyse", [
      C("m-deriv", "Dérivation", [
        ["m-der-taux", "Taux de variation, nombre dérivé, tangente", ["m-2d-forme"], "Vitesse instantanée d'une voiture"],
        ["m-der-fct", "Fonction dérivée, opérations", ["m-der-taux"], "i = C·du/dt dans un condensateur"],
        ["m-der-var", "Variations et extremums", ["m-der-fct", "m-2d-signe"], "Point de puissance maximale"],
      ]),
      C("m-expo", "Fonction exponentielle", [
        ["m-exp-def", "Définition, propriétés algébriques", ["m-der-fct"], "Charge d'un circuit RC"],
        ["m-exp-etude", "Étude, e^(kx), lien avec les suites géométriques", ["m-exp-def", "m-suites-geo"], ""],
      ]),
      C("m-trigo", "Fonctions trigonométriques", [
        ["m-trig-cercle", "Cercle trigonométrique, radian, enroulement", [], "Angle d'un moteur, PWM servo"],
        ["m-trig-fct", "Fonctions cosinus et sinus", ["m-trig-cercle"], "Courant alternatif 230 V 50 Hz"],
      ]),
    ]),
    T("Géométrie", [
      C("m-prodscal", "Produit scalaire", [
        ["m-ps-def", "Définitions, propriétés", [], "Travail d'une force"],
        ["m-ps-app", "Al-Kashi, applications", ["m-ps-def"], ""],
      ]),
      C("m-geore", "Géométrie repérée", [
        ["m-geo-droite", "Vecteur normal, équation de droite", ["m-ps-def"], ""],
        ["m-geo-cercle", "Équation de cercle, parabole", ["m-geo-droite", "m-2d-forme"], ""],
      ]),
    ]),
    T("Probabilités et statistiques", [
      C("m-proba", "Probabilités conditionnelles et indépendance", [
        ["m-pc-cond", "Probabilité conditionnelle, arbres", [], "Taux de défaut d'une carte électronique"],
        ["m-pc-totales", "Probabilités totales, indépendance", ["m-pc-cond"], ""],
      ]),
      C("m-va", "Variables aléatoires réelles", [
        ["m-va-loi", "Loi, espérance, variance, écart type", ["m-pc-cond"], "Bruit de mesure d'un capteur"],
      ]),
    ]),
  ],
  pc: [
    T("Constitution et transformations de la matière", [
      C("pc-suivi", "Suivi de l'évolution d'un système", [
        ["pc-mole", "Quantité de matière, concentration", [], ""],
        ["pc-avancement", "Avancement, tableau d'avancement, réactif limitant", ["pc-mole"], ""],
        ["pc-titrage", "Dosage par titrage", ["pc-avancement"], ""],
        ["pc-redox", "Oxydoréduction", ["pc-mole"], "Batteries lithium, piles"],
      ]),
      C("pc-structure", "Structure des entités", [
        ["pc-lewis", "Schéma de Lewis, géométrie, polarité", [], ""],
        ["pc-cohesion", "Cohésion des solides, solubilité", ["pc-lewis"], ""],
      ]),
      C("pc-orga", "Chimie organique", [
        ["pc-orga-groupes", "Groupes caractéristiques, nomenclature", [], ""],
        ["pc-combustion", "Combustions, énergie", ["pc-avancement"], "Moteur thermique"],
      ]),
    ]),
    T("Mouvement et interactions", [
      C("pc-champs", "Interactions fondamentales et champs", [
        ["pc-coulomb", "Loi de Coulomb, champ électrostatique", [], "Condensateur"],
        ["pc-gravit", "Interaction gravitationnelle, champ", [], ""],
      ]),
      C("pc-meca", "Description d'un fluide au repos / mouvement", [
        ["pc-pression", "Pression, loi fondamentale de la statique des fluides", [], "Freins hydrauliques"],
        ["pc-newton2", "Variation du vecteur vitesse et 2e loi de Newton (approche)", [], "Accélération d'une voiture"],
      ]),
    ]),
    T("L'énergie : conversions et transferts", [
      C("pc-elec", "Aspects énergétiques des phénomènes électriques", [
        ["pc-courant", "Intensité, tension, loi d'Ohm", [], "Résistance de LED sur ESP32"],
        ["pc-puissance", "Puissance, énergie, effet Joule, rendement", ["pc-courant"], "Autonomie d'une voiture électrique"],
        ["pc-generateur", "Modèle de la source réelle de tension", ["pc-courant"], ""],
      ]),
      C("pc-energie-meca", "Aspects énergétiques des phénomènes mécaniques", [
        ["pc-ec", "Énergie cinétique, théorème de l'énergie cinétique", ["pc-newton2"], "Distance de freinage"],
        ["pc-em", "Énergie potentielle, énergie mécanique", ["pc-ec"], ""],
      ]),
    ]),
    T("Ondes et signaux", [
      C("pc-ondes", "Ondes mécaniques", [
        ["pc-onde-prog", "Onde progressive, célérité, retard", [], "Capteur ultrason HC-SR04"],
        ["pc-onde-perio", "Ondes périodiques, longueur d'onde", ["pc-onde-prog"], ""],
      ]),
      C("pc-optique", "Images et couleurs, lumière", [
        ["pc-lentille", "Lentille mince, relation de conjugaison", [], "Caméra ESP32-CAM"],
        ["pc-couleur", "Couleurs, synthèse additive/soustractive", [], "LED RGB"],
        ["pc-photon", "Modèle corpusculaire, photon, énergie", [], ""],
      ]),
    ]),
  ],
  si: [
    T("Créer des produits innovants", [
      C("si-demarche", "Démarche de projet et cahier des charges", [
        ["si-cdc", "Besoin, cahier des charges, diagrammes SysML (exigences, cas d'utilisation)", [], "Projet ESP32"],
      ]),
    ]),
    T("Analyser les produits existants", [
      C("si-sysml", "Modélisation SysML", [
        ["si-bdd", "Diagrammes de blocs, chaînes de puissance et d'information", [], "Voiture : batterie → onduleur → moteur"],
        ["si-etats", "Diagrammes d'états, séquence", ["si-bdd"], "Programme embarqué"],
      ]),
    ]),
    T("Modéliser et simuler", [
      C("si-meca", "Mécanique", [
        ["si-statique", "Actions mécaniques, PFS", [], "Effort sur un bras de suspension"],
        ["si-cinematique", "Cinématique, liaisons, schéma cinématique", [], "Transmission, réducteur"],
        ["si-energie", "Puissance, rendement d'une chaîne", ["pc-puissance"], ""],
      ]),
      C("si-elec", "Électricité et électronique", [
        ["si-lois", "Lois de Kirchhoff, diviseur de tension", ["pc-courant"], "Lecture de capteur analogique"],
        ["si-moteur", "Moteur à courant continu, hacheur, PWM", ["si-lois"], "Pilotage moteur avec ESP32"],
      ]),
      C("si-info", "Information numérique", [
        ["si-numeration", "Numération binaire/hexadécimale, codage", [], "Registres, couleurs RGB"],
        ["si-logique", "Logique combinatoire, algorithmes", ["si-numeration"], ""],
        ["si-prog", "Programmation (Python/Arduino), réseaux, protocoles", ["si-logique"], "ESP32 WiFi/MQTT"],
      ]),
    ]),
    T("Expérimenter", [
      C("si-mesure", "Mesures et écarts", [
        ["si-ecarts", "Écarts entre réel, simulé, attendu", [], ""],
      ]),
    ]),
  ],
  fr: [
    T("Bac de français (oral + écrit)", [
      C("fr-methodo", "Méthodes de l'épreuve", [
        ["fr-comm", "Commentaire de texte", [], ""],
        ["fr-dissert", "Dissertation sur œuvre", [], ""],
        ["fr-oral", "Explication linéaire et entretien oral", [], ""],
        ["fr-grammaire", "Question de grammaire", [], ""],
      ]),
      C("fr-objets", "Objets d'étude (œuvres au programme 2026-2027)", [
        ["fr-poesie", "La poésie du XIXe au XXIe siècle", [], ""],
        ["fr-roman", "Le roman et le récit du Moyen Âge au XXIe siècle", [], ""],
        ["fr-theatre", "Le théâtre du XVIIe au XXIe siècle", [], ""],
        ["fr-idees", "La littérature d'idées du XVIe au XVIIIe siècle", [], ""],
      ]),
    ]),
  ],
  hg: [
    T("Histoire", [C("hg-h", "Histoire (1789-1914)", [
      ["hg-revol", "L'Europe face aux révolutions", []], ["hg-fr19", "La France dans l'Europe des nationalités", []],
      ["hg-indus", "L'industrialisation et l'accélération des transformations", [], "Naissance de l'automobile"],
      ["hg-ww1", "La Première Guerre mondiale", []],
    ])]),
    T("Géographie", [C("hg-g", "Géographie : dynamiques d'un monde en recomposition", [
      ["hg-metro", "La métropolisation", []], ["hg-prod", "Une diversification des espaces productifs", []],
      ["hg-rural", "Les espaces ruraux", []], ["hg-chine", "La Chine : des recompositions spatiales multiples", []],
    ])]),
  ],
  ang: [T("Axes culturels", [C("ang-axes", "Gestes fondateurs, innovations scientifiques…", [
    ["ang-innov", "Innovations scientifiques et responsabilité", [], "Tech vocabulary"],
    ["ang-ecrit", "Expression écrite et compréhension", []],
  ])])],
  es: [T("Enseignement scientifique", [C("es-ch", "Thèmes", [
    ["es-energie", "Le Soleil, notre source d'énergie", []], ["es-terre", "La Terre, un astre singulier", []],
    ["es-son", "Son et musique", []], ["es-elements", "Une longue histoire de la matière", []],
  ])])],
};

export function toutesNotions() {
  const out = [];
  for (const [mat, themes] of Object.entries(PROGRAMME))
    for (const th of themes) for (const ch of th.chapitres) ch.notions.forEach((n, i) =>
      out.push({ ...n, matiere: mat, theme: th.theme, chapitre: ch.id, chapitreTitre: ch.titre, ordreOfficiel: out.length }));
  return out;
}

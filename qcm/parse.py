import json, re, unicodedata

raw = open('pdf.txt', encoding='utf-8').read()

# Retire les marqueurs de page : le texte des questions traverse les pages.
raw = re.sub(r'^=== PAGE \d+ ===$', '', raw, flags=re.M)

# Recolle les mots coupes en fin de ligne (ex. "se pencher au-\ndessus").
raw = re.sub(r'(\w)-\n(\w)', r'\1-\2', raw)

LABELS = ['Vérification', 'Sécurité routière', 'Premiers secours']
KEYS = ['verification', 'securite', 'secours']

# Decoupe en blocs "Question n°NN"
blocs = re.split(r'\bQuestion n°(\d{2})\b', raw)
assert len(blocs) == 201, len(blocs)

def nettoie(t):
    t = t.replace('\n', ' ')
    t = t.replace('’', "'").replace(' ', ' ')
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip(' •●-')

def coupe(t):
    """Separe l'enonce (l'ordre donne par l'inspecteur) de la reponse."""
    # 1er cas : l'enonce est une question -> il finit au premier '?'
    m = re.search(r'\?', t)
    # 2e cas : il finit au premier '.' suivi d'une majuscule ou d'un chiffre de liste
    m2 = re.search(r'\.\s+(?=[A-ZÀÉÈÊÎÔÜÇ0-9])', t)
    if m and (not m2 or m.start() < m2.start()):
        return t[:m.end()].strip(), t[m.end():].strip()
    if m2:
        return t[:m2.start() + 1].strip(), t[m2.end():].strip()
    return t.strip(), ''

# Consignes qui suivent parfois le '?' et appartiennent encore a l'enonce.
SUITE = re.compile(r"^((?:Citez|Donnez|Nommez|Expliquez|Précisez|Indiquez|Justifiez)"
                   r"[^.?]{0,60}[.?])\s*")

def recolle_consigne(enonce, reponse):
    m = SUITE.match(reponse)
    if m:
        return (enonce + ' ' + m.group(1)).strip(), reponse[m.end():].strip()
    return enonce, reponse

questions = []
for i in range(1, len(blocs), 2):
    num = blocs[i]
    corps = blocs[i + 1]
    # coupe le pied de page final
    corps = corps.split('Fiche complète —')[0]

    # positions des trois labels
    pos = []
    for lab in LABELS:
        m = re.search(re.escape(lab) + r'\s*[—–-]\s*', corps)
        assert m, (num, lab)
        pos.append((m.start(), m.end(), lab))
    pos.sort()

    item = {'n': num}
    for j, (s, e, lab) in enumerate(pos):
        fin = pos[j + 1][0] if j + 1 < len(pos) else len(corps)
        texte = nettoie(corps[e:fin])
        enonce, reponse = coupe(texte)
        enonce, reponse = recolle_consigne(enonce, reponse)
        k = KEYS[LABELS.index(lab)]
        item[k] = {'q': enonce, 'a': reponse}
    questions.append(item)

assert len(questions) == 100
assert [q['n'] for q in questions] == ['%02d' % i for i in range(100)]

# Controle qualite : signale les decoupes suspectes
for q in questions:
    for k in KEYS:
        a = q[k]['a']
        if len(a) < 25:
            print('COURT  %s/%s : Q=%r A=%r' % (q['n'], k, q[k]['q'], a))
        if len(q[k]['q']) > 160:
            print('LONG   %s/%s : Q=%r' % (q['n'], k, q[k]['q'][:170]))

json.dump(questions, open('questions.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('OK ->', len(questions), 'questions')

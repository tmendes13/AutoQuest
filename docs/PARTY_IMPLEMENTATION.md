# Party Deliberation — Comunicação e Tomada de Decisão

Resumo das alterações desta iteração: a party de jogadores deixa de
responder individualmente ao GM e passa a fazer uma **discussão interna
síncrona** para produzir uma única resposta oficial por turno.

---

## 1. Objetivo

Quando o Game Master envia uma nova mensagem, é automaticamente iniciada
uma ronda de discussão entre os jogadores. O grupo:

1. propõe individualmente o que cada um faria,
2. compila as propostas,
3. escolhe aleatoriamente um jogador para sintetizar uma proposta inicial,
4. faz circular essa proposta pelos restantes, com um budget de modificações
   por jogador,
5. termina por **consenso implícito** (uma volta completa sem alterações)
   ou por **exaustão de budget** (ninguém ainda pode modificar),
6. envia a proposta final ao GM como resposta do grupo.

Os jogadores **lêem** a memória validada do GM (`memory.json`), mas **nunca
escrevem**. A escrita continua a ser responsabilidade exclusiva do Memory
Keeper.

---

## 2. Ficheiros novos

| Ficheiro | Papel |
|----------|-------|
| `agents/party.py` | Orquestrador da deliberação. Expõe `deliberate(party, gm_message, memory_path)`. |
| `docs/party_deliberation.md` | Este documento. |

## 3. Ficheiros alterados

| Ficheiro | O que mudou |
|----------|-------------|
| `agents/player.py` | Adicionadas `propose`, `synthesize`, `review` e o parser `_parse_review`. `act` mantém-se (legado). |
| `agents/gm/gm.py` | `run_turn(gm, party, situation)` agora recebe `list[Player]` e chama `deliberate`. Label do MK passa a `"party"`. Excepção de exaustão usa `actor="party"`. |
| `main.py` | Acrescentado o player Aelindra (Elf Mage). A `party = [thorin, aelindra]` é passada a `run_turn`. System prompt comum a todos via `_player_system_prompt`. |

---

## 4. Algoritmo da deliberação (em `agents/party.py`)

```
deliberate(party, gm_message, memory_path, max_modifications=3):
    validated_facts = memory_store.format_validated(memory_path)

    # 1. Cada player faz um draft independente.
    for p in party:
        proposals[p.name] = propose(p, gm_message, validated_facts)

    # Corner case: 1 só player -> a sua proposta é a final.
    if len(party) == 1:
        return proposals[only.name]

    # 2. Starter aleatório.
    starter = random.choice(party)

    # 3. Starter sintetiza a primeira proposta de grupo.
    current = synthesize(starter, gm_message, format(proposals), facts)

    # 4. Circulação.
    remaining = {p.name: max_modifications for p in party}
    last_modifier = starter.name

    while True:
        queue = everyone_except(last_modifier)
        queue.sort(by=-remaining[p.name])   # mais budget primeiro
        random.shuffle(ties)                # variar ordem entre rondas

        modified = False
        for reviewer in queue:
            if remaining[reviewer.name] == 0:
                # auto-aprova (não pode modificar)
                continue
            verdict, new_proposal = review(reviewer, gm_message, current, facts)
            if verdict == APPROVE:
                continue
            # MODIFY
            current = new_proposal
            remaining[reviewer.name] -= 1
            last_modifier = reviewer.name
            modified = True
            break  # reinicia a circulação

        if not modified:
            break  # consenso implícito ou budget esgotado

    return current
```

### Pontos-chave do desenho

- **Starter aleatório por ronda** (`random.choice`) impede que um padrão
  fixo domine a conversa.
- **Queue ordenada por budget restante**, com **shuffle nos empates**,
  prioriza quem ainda pode contribuir e mantém variabilidade entre rondas.
- **MODIFY consome 1 slot** do `max_modifications` do modificador (default
  3). Quando esgota, qualquer turno dele é tratado como APPROVE implícito.
- **Re-circulação após cada modificação**: o modificador sai da queue, e
  todos os outros (incluindo o starter original) re-revêm a versão nova.
- **Consenso implícito**: termina quando uma volta inteira passa sem
  qualquer MODIFY. Cobre tanto "todos aprovaram" como "todos sem budget".

---

## 5. Funções novas em `agents/player.py`

Todas recebem `validated_facts` (texto já formatado pela `memory_store`) em
vez de lerem a memória diretamente — separação clara: a deliberação fala
com o memory_store, o player recebe contexto pronto.

- `propose(player, gm_message, validated_facts) -> str`
  Draft individual, 1-3 frases, primeira pessoa.

- `synthesize(player, gm_message, proposals_block, validated_facts) -> str`
  O starter combina/escolhe ideias e devolve UMA proposta em
  primeira pessoa plural.

- `review(player, gm_message, current_proposal, validated_facts) -> (verdict, new_proposal)`
  O LLM responde estritamente:
  ```
  DECISION: APPROVE
  ```
  ou
  ```
  DECISION: MODIFY
  NEW_PROPOSAL: <texto da nova proposta>
  ```
  O parser `_parse_review` é tolerante a maiúsculas/minúsculas e a respostas
  malformadas. Heurísticas defensivas:
  - sem `DECISION:` claro → APPROVE (não inventa mudanças),
  - `MODIFY` sem `NEW_PROPOSAL` utilizável → APPROVE (não apaga a proposta).

---

## 6. Integração com o GM (`agents/gm/gm.py`)

```python
def run_turn(gm, party: list[Player], situation: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        party_response, _log = deliberate(party, situation, gm.memory_path)
        is_valid, _ = _ingest_with_arbitration(
            gm, author="party", raw_text=party_response
        )
        if is_valid:
            break
    else:
        raise GMRetriesExhaustedError(
            actor="party", last_text=party_response, last_reason=...
        )

    # Narrator continua exatamente como antes:
    # narrate -> mem_keep(author="narrator") -> arbitrate -> retry/abort
```

O label `"party"` é a constante `PARTY_AUTHOR` em `gm.py`, usada no
`mem_keep` e na excepção de exaustão. Cada entrada na `memory.json`
continua com o formato `[validated/not validated] [author] (id=...):
content`, agora podendo aparecer `[party]`.

---

## 7. Players hardcoded em `main.py`

```python
thorin   = Player("Thorin",   "Dwarf", Class("Warrior", 10), "Brave and impulsive",   max_hp=40)
aelindra = Player("Aelindra", "Elf",   Class("Mage",    6),  "Curious and calculative", max_hp=25)
party = [thorin, aelindra]
```

System prompt comum aos dois (via `_player_system_prompt`) reforça
colaboração, primeira pessoa, e consistência com os factos validados.

---

## 8. Como funciona um turno completo agora

```
GM-narrator emite situação
        |
        v
+-------- run_turn ----------+
| party.deliberate:          |
|   propose × N              |
|   synthesize (starter)     |
|   circulate (APPROVE/MOD)  |
+----------------------------+
        |
        v
mem_keep(author="party")  --> not validated
        |
        v
arbitrate
   |VALID -> mark validated
   |INVALID -> delete + retry (até MAX_RETRIES, depois aborta)
        v
narrate (lê memória validada)
        |
        v
mem_keep(author="narrator")  --> not validated
        |
        v
arbitrate
   |VALID -> situação devolvida ao próximo turno
   |INVALID -> delete + retry (até MAX_RETRIES, depois aborta)
```

Tudo continua **estritamente síncrono**: zero race conditions no
`memory.json`.

---

## 9. Validações já realizadas

- `python -m py_compile` em todos os ficheiros novos/alterados: **OK**.
- Smoke test do parser `_parse_review` (APPROVE, MODIFY, malformado,
  MODIFY sem texto): **OK**.
- Smoke test end-to-end de `deliberate` com chats fake:
  - **Consenso após 1 MODIFY**: starter sintetiza → 1 reviewer modifica
    (budget 3→2) → starter re-aprova → final = versão modificada. ✅
  - **Exaustão de budget**: 2 jogadores a fazerem MODIFY alternado até
    ambos terem 0 → próximo turno = implicit APPROVE → consenso. Foram
    feitas as 6 modificações esperadas (3 por jogador). ✅

---

## 10. Escalabilidade

A `deliberate` aceita qualquer `list[Player]` e não tem assumções de
tamanho. Pontos de configuração:

- `MAX_MODIFICATIONS` (default 3) — pode ser passado por turno via
  parâmetro `max_modifications` de `deliberate`.
- O número de calls ao LLM por turno cresce como
  `N + 1 + min(N × MAX_MODIFICATIONS, …)` (drafts + síntese + reviews).
  Para `N=2, MAX=3`: máximo 9 calls por deliberação.
  Para `N=4, MAX=3`: máximo 17 calls por deliberação.

---

## 11. O que **NÃO** foi tocado nesta iteração

- Criação dinâmica de players (continua hardcoded em `main.py`).
- Sessão zero / criação de personagens pelos jogadores.
- Ficheiro de faltas + condição de fim de jogo por X faltas.
- Memória individual de cada jogador (continua só o chat do LLM).
- Mecânicas determinísticas (dados, dano programático).

Estes ficam para iterações seguintes; estão no `Ideas.txt`.

# GM — Implementação Síncrona com Memória Validada

Resumo do que foi implementado nesta iteração para o Game Master da AutoQuest.

---

## 1. Objetivo

Reescrever o GM como **três sub-agentes síncronos** a partilhar **um único
ficheiro de memória**, com um ciclo de validação para evitar que ações
alucinadas (do jogador ou do narrador) entrem na história. Para esta iteração
ficou apenas **um jogador** para isolar o foco no pipeline do GM.

---

## 2. Ficheiros novos

| Ficheiro | Papel |
|----------|-------|
| `agents/gm/memory_store.py` | I/O puro sobre `memory.json`. Sem LLM. |
| `agents/gm/gm.py` | Orquestrador síncrono dos três sub-agentes. |
| `GM_IMPLEMENTATION.md` | Este resumo. |

## 3. Ficheiros reescritos

| Ficheiro | O que mudou |
|----------|-------------|
| `agents/gm/memory_keeper.py` | Agora resume o prompt via LLM e escreve uma entrada `not validated` no ficheiro de memória, com etiqueta de autor. |
| `agents/gm/arbiter.py` | Agora lê a memória, valida UMA entrada `not validated` contra as `validated`, e ou marca-a `validated` ou apaga-a. Foco apenas em alucinações. |
| `agents/gm/narrator.py` | Já não recebe texto do MK; lê o ficheiro de memória (factos validados) e produz a próxima parte da história. |
| `main.py` | Agora cria **apenas um jogador** (Thorin) e usa o novo orquestrador `setup_gm` / `begin_campaign` / `run_turn`. |
| `.gitignore` | Acrescentado `memory.json`. |

---

## 4. Formato do ficheiro de memória (`memory.json`)

```json
{
  "entries": [
    {
      "id": "47948fb5",
      "validated": true,
      "author": "narrator",
      "content": "Resumo factual de 1-4 frases."
    },
    {
      "id": "861d8cba",
      "validated": false,
      "author": "Thorin",
      "content": "Resumo factual da ação do jogador."
    }
  ]
}
```

- **`id`**: hex curto de UUID, único por entrada.
- **`validated`**: `false` significa a etiqueta *not validated*; `true`
  significa que o Arbiter já aceitou a entrada.
- **`author`**: vem **antes** do conteúdo, conforme pedido — etiqueta de quem
  produziu o prompt original (`"narrator"` ou nome do jogador, ex. `"Thorin"`).
- **`content`**: o resumo factual produzido pelo Memory Keeper.

A ordem das etiquetas no formato textual usado pelos LLMs é exatamente a
pedida: `[validated/not validated] [author] (id=...): content`.

---

## 5. Sub-agentes

### 5.1. Memory Keeper (`agents/gm/memory_keeper.py`)
- `setup_mem_keeper()` — cria o chat LLM dedicado com o system prompt de
  resumir factos essenciais.
- `mem_keep(mk_chat, memory_path, author, raw_text) -> entry_id` —
  pede ao LLM um resumo de 1-4 frases e **escreve** a entrada no ficheiro
  de memória com `validated=False` e o `author` recebido. Devolve o `id`.

### 5.2. Arbiter (`agents/gm/arbiter.py`)
- `setup_arbiter()` — cria o chat LLM dedicado com o system prompt focado
  **apenas em alucinações**: o ator tem o objeto/arma que diz usar? está no
  ambiente certo? o inimigo existe? referencia algo que existe?
- `arbitrate(arbiter_chat, memory_path, entry_id) -> (is_valid, raw_text)` —
  lê os factos `validated`, recebe a entrada candidata, pede uma decisão
  estrita no formato `DECISION: VALID|INVALID` + `REASON: …`, e:
  - **VALID** → muda a etiqueta da entrada para `validated`.
  - **INVALID** → apaga a entrada do ficheiro.
- Parser de decisão tolerante a maiúsculas/minúsculas, com fallback
  conservador para *VALID* quando o LLM produz texto malformado, mas
  heurístico para *INVALID* se a palavra aparecer no corpo.

### 5.3. Narrator (`agents/gm/narrator.py`)
- `setup_narrator()` — system prompt focado em continuar a história
  consistentemente com os factos validados, em 3-6 frases.
- `start_campaign(narrator_chat)` — gera a abertura inicial (não há ainda
  memória para ler).
- `narrate(narrator_chat, memory_path)` — lê a memória **validada** do
  ficheiro e gera a próxima situação.

---

## 6. Orquestrador (`agents/gm/gm.py`)

### Estrutura
```python
@dataclass
class GameMaster:
    narrator_chat: object
    mk_chat: object
    arbiter_chat: object
    memory_path: str
```

### API pública
- `setup_gm(memory_path="memory.json")` — reset do ficheiro de memória e
  criação dos três chats LLM.
- `begin_campaign(gm)` — narrador gera a abertura, MK escreve-a e o
  orquestrador marca-a directamente como `validated` (não há nada a
  comparar).
- `run_turn(gm, player, situation) -> nova_situação` — executa o ciclo
  completo descrito a seguir.

### Fluxo síncrono por turno (exatamente como pedido)
```
1. Recebe resposta do player (act(player, situation))
2. memory_keeper -> escreve entrada [Thorin] como NOT VALIDATED
3. arbiter      -> valida ou apaga essa entrada
   ├── VALID   -> avança para 4
   └── INVALID -> delete_unvalidated() e volta a 1 (re-pergunta ao player)
4. narrator     -> lê memória validada e gera nova situação
5. memory_keeper -> escreve entrada [narrator] como NOT VALIDATED
6. arbiter       -> valida ou apaga essa entrada
   ├── VALID   -> devolve a narração ao caller (que a passa ao player)
   └── INVALID -> delete_unvalidated() e volta a 4 (re-pergunta ao narrator)
```

Tudo é estritamente síncrono — uma chamada de cada vez ao ficheiro — pelo que
**não existem race conditions** (a `memory.json` nunca é tocada por dois
agentes ao mesmo tempo).

### Retries
Cada *loop de invalidação* tem `MAX_RETRIES = 3` para evitar ciclos infinitos.
Se esgotarem, o turno continua mesmo sem entrada validada (o jogo prossegue
em vez de bloquear).

---

## 7. Como correr

```powershell
# Pré-requisitos: Ollama a correr e o modelo já transferido
ollama pull gpt-oss:20b-cloud

# Ambiente Python
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Correr o jogo (1 player, 5 rondas)
python main.py
```

Durante a execução é gerado um ficheiro `memory.json` na raiz do projeto que
mostra, em tempo real, o estado da memória partilhada do GM. Está
`.gitignore`-d.

---

## 8. Validações já feitas

- `python -m py_compile` em todos os ficheiros novos/reescritos: **OK**.
- Imports do orquestrador (`from agents.gm.gm import setup_gm, begin_campaign,
  run_turn`): **OK**.
- Smoke test do `memory_store` (init → append → validate → delete →
  delete_unvalidated): **OK**.
- Testes ao parser do Arbiter (`_parse_decision`) com inputs VALID, INVALID,
  case-insensitive, malformado, heurístico: **OK**.

---

## 9. O que NÃO foi tocado nesta iteração

Por foco e conforme pedido:
- Pipeline cognitivo do jogador (observação → reflexão → planeamento) —
  o jogador continua a agir directamente sobre a situação.
- Mecânicas de jogo (dados, dano programático, inventário real).
- Múltiplos jogadores e coordenação entre eles.
- Jogador humano.
- Bugs antigos cosméticos nos modelos (`Item.descripion`, `Player.status()`
  com "Iventory", `is_alive()` sem `else`).

Estes ficam para iterações seguintes.

---

## 10. Pontos de extensão imediatos

- **Ligação ao estado estruturado dos `Player`**: o `arbitrate` poderia
  receber também o inventário programático (`player.inventory`, `player.weapon`)
  para uma verificação determinística de posse antes da chamada ao LLM.
- **Logging estruturado** em vez de `print` espalhado.
- **Memória do jogador**: na sequência da arquitectura cognitiva, dar ao
  jogador acesso (limitado) à memória validada para reflectir antes de agir.
- **Re-entrar com 2+ jogadores**: o `run_turn` está pensado para um jogador,
  mas o `_ingest_with_arbitration` é genérico — basta iterar os jogadores
  no passo 1 antes de chamar o narrador.

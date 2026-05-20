# Memory Keeper — Memória Compacta e Condensação Periódica

Resumo das alterações desta iteração: o Memory Keeper passou a escrever apenas factos duráveis e a memória validada passou a ser condensada periodicamente para impedir crescimento indefinido do contexto enviado aos LLMs.

---

## 1. Objetivo

Reduzir o tamanho do contexto usado pelo Game Master sem perder consistência narrativa. Antes desta alteração, a memória validada crescia indefinidamente porque cada ação/narração acrescentava novas entradas a `memory.json` e nada removia ou reescrevia factos obsoletos.

A solução implementada combina:

1. extração mais seletiva de factos pelo Memory Keeper,
2. omissão de textos sem factos duráveis,
3. condensação periódica de entradas antigas validadas,
4. chamadas stateless nos sub-agentes do GM para evitar crescimento escondido no histórico dos chats.

---

## 2. Ficheiros novos

| Ficheiro | Papel |
|----------|-------|
| `tests/test_memory_management.py` | Smoke tests para `NO_RELEVANT_FACTS`, condensação e proteção de entradas não validadas. |
| `docs/MEMORY_KEEPER_IMPLEMENTATION.md` | Este resumo. |

## 3. Ficheiros alterados

| Ficheiro | O que mudou |
|----------|-------------|
| `agents/gm/memory_keeper.py` | Prompt mais seletiva, `NO_RELEVANT_FACTS`, constantes de condensação, `should_condense()` e `condense_memory()`. |
| `agents/gm/memory_store.py` | Metadata de condensação, suporte a `kind`, helpers de entradas validadas e substituição por snapshot. |
| `agents/gm/gm.py` | Integra condensação após validações aceites e lida com `mem_keep() -> None`. |
| `agents/gm/arbiter.py` | Usa chamada stateless para não acumular histórico de prompts antigos. |
| `agents/gm/narrator.py` | Usa chamada stateless em `narrate()`. |
| `config.py` | `_Chat.send_message()` aceita `remember=False`; novo helper `send_chat_message()`. |

---

## 4. Problema encontrado

Havia dois crescimentos de contexto:

- **Memória em disco**: `memory.json` acumulava todas as entradas validadas para sempre.
- **Histórico interno dos chats**: `_Chat.messages` em `config.py` acumulava cada prompt e resposta dos sub-agentes.

Apenas condensar `memory.json` não resolveria totalmente o problema, porque `Narrator`, `Arbiter` e `Memory Keeper` continuariam a carregar histórico antigo dentro do chat. Por isso, os sub-agentes GM passaram a usar chamadas `remember=False` quando já recebem explicitamente todo o contexto necessário.

---

## 5. Memory Keeper mais seletivo

### 5.1. Nova política de escrita

O Memory Keeper deve guardar apenas factos que possam afetar consistência futura:

- localização atual ou mudança de local,
- presença de party, NPCs, inimigos ou objetos relevantes,
- objetivos ativos,
- inventário, itens consumidos/perdidos, HP e condições,
- descobertas importantes,
- consequências ainda por resolver.

Deve ignorar:

- prosa e ambiente sem consequência futura,
- emoções/mood sem impacto mecânico ou narrativo,
- contexto repetido,
- planos que não foram executados,
- detalhes temporários já resolvidos.

### 5.2. Sentinela `NO_RELEVANT_FACTS`

Se o texto não acrescentar factos duráveis, o LLM deve responder exatamente:

```text
NO_RELEVANT_FACTS
```

Nesse caso, `mem_keep()` devolve `None` e não escreve uma entrada em `memory.json`.

---

## 6. Condensação periódica

A condensação é acionada por número de entradas validadas, conforme decidido nesta iteração.

Constantes atuais em `agents/gm/memory_keeper.py`:

```python
CONDENSE_AFTER_VALIDATED_ENTRIES = 10
RECENT_VALIDATED_ENTRIES_TO_KEEP = 4
```

Ou seja:

- depois de 10 novas validações desde a última condensação,
- se houver mais de 4 entradas validadas,
- as entradas antigas são condensadas num único snapshot,
- as 4 entradas validadas mais recentes ficam separadas para preservar contexto local.

### 6.1. Estratégia usada

A memória passa a funcionar como:

```text
[summary antigo condensado]
[evento recente 1]
[evento recente 2]
[evento recente 3]
[evento recente 4]
```

Isto segue a ideia de memória longa + memória curta:

- **memória longa**: snapshot condensado do estado persistente,
- **memória curta**: últimos eventos validados, ainda importantes para continuidade imediata.

### 6.2. Factos removidos na condensação

A prompt de condensação pede para remover factos:

- resolvidos,
- obsoletos,
- contraditos por factos mais recentes,
- meramente temporários,
- sobre itens adquiridos e depois consumidos/perdidos, exceto se o estado final ainda importar.

Exemplo: se a party pegou uma granada na ronda 2 e gastou essa granada na ronda 3, na ronda 15 a memória não precisa de manter todo o histórico; basta manter o estado final relevante, se houver algum.

---

## 7. Formato atualizado de `memory.json`

O formato antigo continua compatível. Foi adicionado `metadata` e o campo opcional `kind`.

```json
{
  "entries": [
    {
      "id": "47948fb5",
      "validated": true,
      "author": "memory_keeper",
      "content": "Snapshot condensado do estado atual relevante.",
      "kind": "summary"
    },
    {
      "id": "861d8cba",
      "validated": true,
      "author": "party",
      "content": "A party abre a porta norte e entra na cripta.",
      "kind": "event"
    }
  ],
  "metadata": {
    "validated_since_condense": 1
  }
}
```

Notas:

- `kind="event"` é o default para entradas normais.
- `kind="summary"` identifica snapshots condensados.
- O formato textual enviado aos LLMs manteve-se curto: `[validated/not validated] [author] (id=...): content`.
- Entradas antigas sem `kind` continuam válidas porque o código usa fallback.

---

## 8. Fluxo atualizado no GM

O fluxo de ingestão passou a ser:

```text
raw_text
  -> mem_keep()
      -> NO_RELEVANT_FACTS: não escreve nada, aceita sem arbitrar
      -> entry_id: escreve entrada not validated
  -> arbitrate(entry_id)
      -> INVALID: apaga entrada e limpa not validated restantes
      -> VALID: marca entrada como validated
  -> should_condense()
      -> se sim: condense_memory()
```

A abertura da campanha também lida com `mem_keep() -> None`, embora normalmente deva gerar factos relevantes.

---

## 9. Chamadas stateless

`config.py` agora suporta:

```python
send_chat_message(chat, message, remember=False)
```

Quando `remember=False`:

- o chat envia apenas a system instruction e a mensagem atual,
- não acrescenta o prompt/resposta a `chat.messages`,
- evita crescimento infinito de histórico interno.

Aplicado em:

- `memory_keeper.mem_keep()`;
- `memory_keeper.condense_memory()`;
- `arbiter.arbitrate()`;
- `narrator.narrate()`.

Os players continuam com histórico próprio por agora, porque memória própria/linha de raciocínio do player é uma funcionalidade futura indicada no `Ideas.txt`.

---

## 10. Relação com os papers analisados

### Mem0 — `2504.19413`

Aproveitado:

- extrair e consolidar informação saliente em vez de usar full-context;
- reduzir custo/tokens mantendo coerência.

Não aplicado:

- graph memory, por ser pesado para a arquitetura atual.

### A-MEM — `2502.12110`

Aproveitado:

- ideia de evolução/reescrita de memórias antigas quando entram factos novos.

Não aplicado:

- Zettelkasten completo, tags dinâmicas e rede de links, porque seria complexidade excessiva nesta fase.

### Cognitive Memory in LLMs — `2504.02441`

Aproveitado:

- separação entre memória curta e memória longa;
- seleção/gestão/atualização da memória textual.

Não aplicado:

- KV-cache, LoRA, parameter memory ou hidden-state memory, por não fazerem sentido no escopo atual do projeto.

---

## 11. Validações realizadas

Foram executados com sucesso:

```powershell
python -m py_compile config.py agents/gm/memory_store.py agents/gm/memory_keeper.py agents/gm/gm.py agents/gm/arbiter.py agents/gm/narrator.py tests/test_memory_management.py
python tests/test_memory_management.py
```

Smoke tests cobrem:

- `NO_RELEVANT_FACTS` não escreve entradas;
- condensação substitui entradas antigas por summary + recentes;
- entradas `not validated` não são absorvidas pela condensação;
- chamadas fake usam `remember=False`.

---

## 12. Pontos de extensão futura

- Ajustar `CONDENSE_AFTER_VALIDATED_ENTRIES` e `RECENT_VALIDATED_ENTRIES_TO_KEEP` conforme comportamento real em campanhas maiores.
- Criar métricas simples de tamanho de memória antes/depois da condensação.
- Integrar estado estruturado real de inventário/HP quando forem adicionadas mecânicas determinísticas.
- Criar memória própria dos players sem misturar com a memória validada global do GM.
- Atualizar `GM_IMPLEMENTATION.md` no futuro para refletir este novo estado se esse documento passar a ser tratado como visão consolidada do GM.

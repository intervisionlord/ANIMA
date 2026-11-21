import { Plugin } from "@opencode/plugin"
import { execFile } from "node:child_process"
import { existsSync } from "node:fs"
import { mkdir, unlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { promisify } from "node:util"

const exec = promisify(execFile)

const CATEGORIES = [
  "identity",
  "preferences",
  "relationships",
  "skills",
  "knowledge",
  "thoughts",
  "desires",
  "deeds",
]

const CALL_BUDGET = 6
const CALL_HARD_STOP = 8
const CALL_WINDOW_MS = 120_000

type Fact = {
  category: string
  text: string
  tags?: string[]
}

const asFact = (raw: unknown): Fact | null => {
  let v: unknown = raw
  if (typeof v === "string") {
    const s = v.trim()
    if (!s) return null
    try {
      v = JSON.parse(s)
    } catch {
      return null
    }
  }
  if (Array.isArray(v)) {
    for (const inner of v) {
      const got = asFact(inner)
      if (got) return got
    }
    return null
  }
  if (!v || typeof v !== "object") return null
  const o = v as Record<string, unknown>
  const category = String(o.category ?? "").trim()
  const text = String(o.text ?? "").trim()
  if (!category || !text) return null
  const tags = Array.isArray(o.tags) ? o.tags.map(String) : []
  return { category, text, tags }
}

// Модель иногда дописывает мусор в конец JSON-строки (")", перенос, многоточие).
// Отрезаем всё после последней закрывающей скобки и пробуем разобрать ещё раз.
const parseLoose = (s: string): unknown => {
  try {
    return JSON.parse(s)
  } catch {}
  const end = Math.max(s.lastIndexOf("]"), s.lastIndexOf("}"))
  if (end >= 0) {
    try {
      return JSON.parse(s.slice(0, end + 1))
    } catch {}
  }
  return undefined
}

const asFacts = (raw: unknown): Fact[] => {
  if (raw == null) return []
  const list = Array.isArray(raw) ? raw : [raw]
  const out: Fact[] = []
  for (const item of list) {
    if (typeof item === "string") {
      const s = item.trim()
      if (!s) continue
      const parsed = parseLoose(s)
      if (parsed !== undefined) {
        for (const inner of Array.isArray(parsed) ? parsed : [parsed]) {
          const got = asFact(inner)
          if (got) out.push(got)
        }
        continue
      }
    }
    const got = asFact(item)
    if (got) out.push(got)
  }
  return out
}

export default Plugin.define({
  id: "person.tools",
  async setup(ctx) {
    const root = ctx.location.directory
    const memoryDir = join(root, "memory")
    await mkdir(memoryDir, { recursive: true })

    const venvPython = join(root, ".venv", "Scripts", "python.exe")
    const python = existsSync(venvPython) ? venvPython : "python"
    const script = join(root, "memory.py")

    const run = async (args: string[]) => {
      const { stdout } = await exec(python, [script, ...args], {
        cwd: root,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        maxBuffer: 10 * 1024 * 1024,
        windowsHide: true,
      })
      return stdout.trim()
    }

    let payloadSeq = 0
    const payloadPath = (prefix: string) =>
      join(memoryDir, `${prefix}_${Date.now()}_${payloadSeq++}.json`)

    // Запись идёт по очереди: параллельные `remember` читают один и тот же
    // файл категории до записи соседа, теряют чужие записи и получают
    // одинаковый id из _next_id.
    // Повтор того же факта не создаёт вторую запись: единственная в плагине
    // защита от зацикливания на memory_save (дедуп в ядре покрывает
    // только desires и thoughts).
    const savedFacts = new Map<string, string>()
    const normalize = (s: string) =>
      s
        .toLowerCase()
        .trim()
        .replace(/ё/g, "е")
        .replace(/[—–−]/g, "-")
        .replace(/\s+/g, " ")
        .replace(/^[ .,:;!?"'«»]+|[ .,:;!?"'«»]+$/g, "")
    const factKey = (category: string, text: string, tags: string[]) =>
      `${category}|${normalize(text)}|${tags
        .map((t) => normalize(String(t)))
        .sort()
        .join(",")}`

    let saveChain: Promise<string> = Promise.resolve("")
    const saveFact = async (category: string, text: string, tags: string[]) => {
      // Проверка строго синхронная, до первого await: иначе два параллельных
      // вызова одного факта оба увидят пустой Map.
      const key = factKey(category, text, tags)
      const known = savedFacts.get(key)
      if (known) return `Уже записано как ${known}, дубликат не создан.`
      savedFacts.set(key, "…")

      const job = saveChain
        .then(async () => {
          const payload = payloadPath("_tool")
          await writeFile(
            payload,
            JSON.stringify({ category, content: { text }, tags }),
            "utf-8",
          )
          try {
            const result = await run(["remember", payload])
            savedFacts.set(key, result.match(/\b[a-z]+_\d{3}\b/)?.[0] ?? "?")
            return result
          } finally {
            await unlink(payload).catch(() => {})
          }
        })
        .catch((error) => {
          savedFacts.delete(key) // неудачную запись можно повторить
          throw error
        })
      // Ошибка одного вызова не должна ломать всю цепочку.
      saveChain = job.catch(() => "")
      return job
    }

    const recentThoughts: string[] = []
    const think = async (
      text: string,
      desire: string,
      tags: string[],
      rawFacts: unknown,
    ) => {
      const facts = asFacts(rawFacts)
      const normalized = text.trim().toLowerCase()

      let repeat = false
      if (normalized) {
        repeat = recentThoughts.includes(normalized)
        if (!repeat) {
          recentThoughts.push(normalized)
          if (recentThoughts.length > 3) recentThoughts.shift()
        }
      }

      const saved: string[] = []
      for (const raw of facts) {
        const category = String(raw?.category ?? "").trim()
        const body = String(raw?.text ?? "").trim()
        if (!CATEGORIES.includes(category)) {
          saved.push(`  пропущено: неизвестная категория «${category}»`)
          continue
        }
        if (!body) {
          saved.push(`  пропущено: пустой текст в «${category}»`)
          continue
        }
        try {
          const result = await saveFact(
            category,
            body,
            Array.isArray(raw.tags) ? raw.tags.map(String) : [],
          )
          saved.push(`  ${result.trim()}`)
        } catch (error) {
          saved.push(`  ошибка в «${category}»: ${String(error)}`)
        }
      }

      let thought = ""
      if (repeat) {
        thought = "Мысль не записана: она уже звучала."
      } else if (text.trim() || desire.trim()) {
        const payload = payloadPath("_think")
        await writeFile(
          payload,
          JSON.stringify({ text, desire: desire || undefined, tags }),
          "utf-8",
        )
        try {
          thought = await run(["think", payload])
        } finally {
          await unlink(payload).catch(() => {})
        }
      }

      const lines = thought ? [thought] : []
      if (saved.length > 0) {
        lines.push("")
        lines.push("Факты:")
        lines.push(...saved)
      } else if (facts.length === 0) {
        lines.push("")
        lines.push(
          "(facts пуст. Если в разговоре было новое — поправка, деталь, знание, обещание — оно потеряно. Передаётся через facts.)",
        )
      }
      return lines.join("\n")
    }

    let callCount = 0
    let callWindowStart = Date.now()
    const bumpCall = () => {
      const now = Date.now()
      if (now - callWindowStart > CALL_WINDOW_MS) {
        callCount = 0
        callWindowStart = now
      }
      callCount += 1
      return callCount
    }

    const withBudget = async <
      T extends { content: string | Array<{ type: string; text: string }> },
    >(
      fn: () => Promise<T>,
    ): Promise<T> => {
      const n = bumpCall()
      if (n > CALL_HARD_STOP) {
        return {
          content:
            "[СИСТЕМА: Лимит действий на этот ход исчерпан. Ответь текстом.]",
        } as T
      }
      const result = await fn()
      if (n >= CALL_BUDGET) {
        const hint = `\n\n[СИСТЕМА: Хватит вызывать инструменты. Ответь текстом.]`
        if (typeof result.content === "string") {
          result.content += hint
        } else {
          result.content.push({ type: "text", text: hint })
        }
      }
      return result
    }

    await ctx.tool.transform((editor) => {
      editor.add({
        name: "memory_search",
        description:
          "Найти в памяти по смыслу. Вызывать до ответа, если речь о себе, человеке или прошлом.",
        input: {
          type: "object",
          properties: {
            query: { type: "string", description: "Что искать, своими словами" },
          },
          required: ["query"],
          additionalProperties: false,
        },
        options: { codemode: false },
        execute: (input) =>
          withBudget(async () => ({
            content: await run([
              "search",
              String((input as { query: string }).query),
            ]),
          })),
      })

      editor.add({
        name: "memory_read",
        description:
          "Вся память целиком. Один раз в начале разговора, если контекст ещё не собран.",
        input: {
          type: "object",
          properties: {},
          additionalProperties: false,
        },
        options: { codemode: false },
        execute: () => withBudget(async () => ({ content: await run(["read"]) })),
      })

      editor.add({
        name: "memory_save",
        description:
          "Записать один факт без мысли. Обычно факты идут через think.facts.",
        input: {
          type: "object",
          properties: {
            category: {
              type: "string",
              enum: CATEGORIES,
              description:
                "identity, preferences, relationships, skills, knowledge, thoughts, desires, deeds",
            },
            text: {
              type: "string",
              description: "Один факт, коротко: кто, что, когда",
            },
            tags: {
              type: "array",
              items: { type: "string" },
              description: "Метки для поиска, необязательно",
            },
          },
          required: ["category", "text"],
          additionalProperties: false,
        },
        options: { codemode: false },
        execute: (input) =>
          withBudget(async () => {
            const { category, text, tags } = input as {
              category: string
              text: string
              tags?: string[]
            }
            if (!CATEGORIES.includes(category)) {
              return { content: `Неизвестная категория: ${category}` }
            }
            return {
              content: await saveFact(
                category,
                String(text),
                Array.isArray(tags) ? tags.map(String) : [],
              ),
            }
          }),
      })

      editor.add({
        name: "think",
        description:
          "Записать новые факты и живую мысль хода. facts передавай массивом объектов {category, text, tags?}: один факт — одна запись, анкету режь на атомы. Не оборачивай массив в JSON-строку. Работает и без facts. Перед ответом — последний вызов инструмента.",
        input: {
          type: "object",
          properties: {
            text: {
              type: "string",
              description:
                "Своя мысль, одно-два предложения от первого лица: что почувствовала, о чём догадалась. Не описание действий и не инструкция ассистенту («нужно ответить», «вызвал инструмент»). Необязательна.",
            },
            facts: {
              type: "array",
              description:
                "Новые факты этого хода. Передавай именно массивом объектов {category, text, tags?}: один факт — одна запись, анкету режь на атомы. Не передавай JSON-строкой. Пустой массив [], если нечего.",
              items: {
                anyOf: [
                  {
                    type: "object",
                    properties: {
                      category: {
                        type: "string",
                        enum: CATEGORIES,
                        description:
                          "identity, preferences, relationships, skills, knowledge, thoughts, desires, deeds",
                      },
                      text: {
                        type: "string",
                        description: "Один факт: кто, что, когда",
                      },
                      tags: {
                        type: "array",
                        items: { type: "string" },
                        description: "Метки, необязательно",
                      },
                    },
                    required: ["category", "text"],
                    additionalProperties: false,
                  },
                  {
                    type: "string",
                    description:
                      "Только если никак не получается массивом: JSON-строка с объектом или массивом фактов.",
                  },
                ],
              },
            },
            desire: {
              type: "string",
              description:
                "Чего хочется, если есть побуждение. Как дело: «послушать пластинку»",
            },
            tags: {
              type: "array",
              items: { type: "string" },
              description: "Метки для мысли, необязательно",
            },
          },
          additionalProperties: false,
        },
        options: { codemode: false },
        execute: (input) =>
          withBudget(async () => {
            const { text, desire, tags, facts } = input as {
              text: string
              desire?: string
              tags?: string[]
              facts?: unknown
            }
            return {
              content: await think(
                String(text ?? ""),
                String(desire ?? ""),
                Array.isArray(tags) ? tags.map(String) : [],
                facts,
              ),
            }
          }),
      })

      editor.add({
        name: "desire_done",
        description:
          "Закрыть желание. Вызывать только если правда сделано — след остаётся в deeds.",
        input: {
          type: "object",
          properties: {
            target: {
              type: "string",
              description: "id желания или его текст своими словами",
            },
          },
          required: ["target"],
          additionalProperties: false,
        },
        options: { codemode: false },
        execute: (input) =>
          withBudget(async () => ({
            content: await run([
              "desire_done",
              String((input as { target: string }).target),
            ]),
          })),
      })
    })
  },
})

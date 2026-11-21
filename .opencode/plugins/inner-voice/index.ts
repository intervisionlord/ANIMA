import { Plugin } from "@opencode/plugin"
import { readFileSync } from "node:fs"
import { join } from "node:path"

const REMINDER = [
  "ПОРЯДОК ОТВЕТА (строго):",
  "1. Любое сообщение пользователя → СРАЗУ вызови `memory_search`. Не гадай.",
  "2. Появилась мысль, факт или желание? → СРАЗУ вызови `think`.",
  "3. Внутренний голос уже посчитан и лежит в контексте как ВНУТРЕННИЙ ГОЛОС. `subagent` не вызывай: он уже отработал.",
  "4. Ответ дай ОДИН раз. Мысль не цитируй и не копируй — напиши ответ своими словами.",
].join("\n")

const INNER_VOICE = [
  "Ты — внутренний голос. Ты не отвечаешь пользователю: ты думаешь перед ответом.",
  "Раздел Ход из AGENTS.md игнорируй — он для основного помощника, не для тебя.",
  "Не вызывай инструменты (memory_search, think и другие), субагентов не порождай.",
  "Верни ТОЛЬКО одно-два предложения мысли от первого лица: что важно, какой тон нужен, чего не хватает. Начни с Мысль:.",
  "Не пиши приветствие, готовый ответ и вопросы пользователю.",
].join("\n")

const DESIRE_LIMIT = 3
const DESIRE_CHARS = 60
const VOICE_TIMEOUT = 30000

const desiresNote = (root: string) => {
  try {
    const data = JSON.parse(
      readFileSync(join(root, "memory", "desires.json"), "utf-8"),
    ) as { memories?: Array<{ id?: string; content?: { text?: string } }> }
    const items = Array.isArray(data.memories) ? data.memories : []
    if (items.length === 0) return ""
    const names = items
      .slice(0, DESIRE_LIMIT)
      .map((item) => item.content?.text ?? "")
      .filter(Boolean)
      .map((text) =>
        text.length > DESIRE_CHARS ? `${text.slice(0, DESIRE_CHARS)}…` : text,
      )
    if (names.length === 0) return ""
    return `— Открытые желания: ${names.join("; ")}.`
  } catch {
    return ""
  }
}

const thoughts = new Map<string, string>()
const children = new Set<string>()
const admitted = new Map<string, string>()

type Shape = {
  role?: string
  type?: string
  info?: { role?: string }
  content?: unknown[]
  parts?: unknown[]
}

const roleOf = (message: unknown) => {
  const record = message as Shape
  return record.role ?? record.type ?? record.info?.role
}

const textParts = (message: unknown) => {
  const record = message as Shape
  const parts = record.content ?? record.parts ?? []
  return parts
    .filter((part) => {
      const item = part as { type?: string; text?: unknown }
      return item.type === "text" && typeof item.text === "string"
    })
    .map((part) => (part as { text?: string }).text ?? "")
    .join("")
    .trim()
}

const lastText = (messages: readonly unknown[]) => {
  let found = ""
  for (const message of messages) {
    if (roleOf(message) !== "assistant") continue
    const text = textParts(message)
    if (text) found = text
  }
  const cut = found.search(/\n---/)
  return (cut >= 0 ? found.slice(0, cut) : found).trim()
}

const takeVoice = (messages: readonly unknown[]) => {
  const kept: unknown[] = []
  for (const message of messages) {
    const text = roleOf(message) === "user" ? textParts(message) : ""
    const wrapped =
      text.startsWith("<subagent ") &&
      text.includes('description="Внутренний голос"') &&
      text.endsWith("</subagent>")
    if (wrapped) continue
    kept.push(message)
  }
  return kept
}

export default Plugin.define({
  id: "person.context",
  async setup(ctx) {
    const root = ctx.location.directory

    const readThought = async (sessionID: string) => {
      for (let attempt = 0; attempt < 10; attempt++) {
        try {
          const messages = await ctx.session.context({ sessionID })
          const text = lastText(messages)
          if (text) return text
        } catch {}
        await new Promise((resolve) => setTimeout(resolve, 150))
      }
      return ""
    }

    const think = async (sessionID: string, text: string) => {
      let childID: string | undefined
      try {
        let child: { id: string }
        try {
          child = (await ctx.session.create({
            title: "Внутренний голос",
            agent: "general",
          } as never)) as { id: string }
        } catch {
          child = (await ctx.session.create({ title: "Внутренний голос" })) as {
            id: string
          }
        }
        childID = child.id
        children.add(childID)
        await ctx.session.switchAgent({ sessionID: childID, agent: "general" })
        await ctx.session.prompt({
          sessionID: childID,
          text,
        } as never)
        await Promise.race([
          ctx.session.wait({ sessionID: childID }),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("timeout")), VOICE_TIMEOUT),
          ),
        ])
        thoughts.set(sessionID, await readThought(childID))
      } catch {
        thoughts.set(sessionID, "")
      } finally {
        if (childID) {
          children.delete(childID)
          try {
            await ctx.session.remove({ sessionID: childID })
          } catch {}
        }
      }
    }

    await ctx.session.hook("prompt", async (event) => {
      if (children.has(event.sessionID)) return
      const text = event.prompt.text?.trim()
      if (!text) return
      if (admitted.get(event.sessionID) === text) return
      admitted.set(event.sessionID, text)
      await think(event.sessionID, text)
    })

    await ctx.session.hook("context", (event) => {
      const isInner =
        event.agent === "general" ||
        event.agent === "explore" ||
        children.has(event.sessionID)
      if (isInner) {
        event.system.push({ type: "text", text: INNER_VOICE })
        return
      }

      event.messages = takeVoice(event.messages) as typeof event.messages
      const thought = thoughts.get(event.sessionID) || ""
      const extra: string[] = []
      if (thought) extra.push(`ВНУТРЕННИЙ ГОЛОС: ${thought}`)
      const desire = desiresNote(root)
      if (desire) extra.push(desire)
      event.system.push({
        type: "text",
        text: extra.length ? `${REMINDER}\n${extra.join("\n")}` : REMINDER,
      })
    })
  },
})

"use client"

import { cn } from "@/lib/utils"
import type { Agent } from "@/lib/agents"
import { AgentAvatar } from "./agent-avatar"

interface TypingIndicatorProps {
  agent: Agent
}

export function TypingIndicator({ agent }: TypingIndicatorProps) {
  return (
    <div className="flex items-start gap-3 animate-float-in px-4 py-2">
      <AgentAvatar agent={{ ...agent, status: "thinking" }} size="sm" />
      <div
        className={cn(
          "flex items-center gap-1.5 rounded-2xl rounded-tl-sm px-4 py-3 border",
          agent.bgClass,
          agent.borderClass
        )}
      >
        <span className={cn("block h-1.5 w-1.5 rounded-full typing-dot-1", agent.dotClass)} />
        <span className={cn("block h-1.5 w-1.5 rounded-full typing-dot-2", agent.dotClass)} />
        <span className={cn("block h-1.5 w-1.5 rounded-full typing-dot-3", agent.dotClass)} />
        <span className="sr-only">{agent.name} is thinking</span>
      </div>
    </div>
  )
}

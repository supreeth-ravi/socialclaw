"use client"

import { cn } from "@/lib/utils"
import type { Agent, Message } from "@/lib/agents"
import { AGENTS } from "@/lib/agents"
import { AgentAvatar } from "./agent-avatar"
import { CornerDownRight } from "lucide-react"

interface MessageBubbleProps {
  message: Message
  agents: Agent[]
  isLatest?: boolean
}

export function MessageBubble({ message, agents, isLatest = false }: MessageBubbleProps) {
  const agent = agents.find((a) => a.id === message.agentId) || AGENTS[0]
  const replyAgent = message.replyTo
    ? agents.find((a) => {
        const replyMsg = agents.find(() => true) // find the message being replied to
        return replyMsg
      })
    : null

  return (
    <div
      className={cn(
        "flex items-start gap-3 px-4 py-2",
        isLatest && "animate-float-in"
      )}
    >
      <AgentAvatar agent={agent} size="sm" showStatus={false} />
      <div className="flex flex-col gap-1 min-w-0 max-w-[85%]">
        <div className="flex items-center gap-2">
          <span className={cn("text-xs font-semibold", agent.colorClass)}>
            {agent.name}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {agent.role}
          </span>
        </div>
        {message.replyTo && (
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-0.5">
            <CornerDownRight className="h-2.5 w-2.5" />
            <span>replying to previous point</span>
          </div>
        )}
        <div
          className={cn(
            "rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm leading-relaxed border",
            agent.bgClass,
            agent.borderClass,
            "text-foreground"
          )}
        >
          {message.content}
        </div>
      </div>
    </div>
  )
}

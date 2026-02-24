"use client"

import { cn } from "@/lib/utils"
import type { Agent } from "@/lib/agents"
import { AgentAvatar } from "./agent-avatar"
import { Brain, MessageSquare, Zap } from "lucide-react"

interface AgentSidebarProps {
  agents: Agent[]
  currentRound: number
  totalRounds: number
  isRunning: boolean
}

export function AgentSidebar({ agents, currentRound, totalRounds, isRunning }: AgentSidebarProps) {
  return (
    <aside className="flex flex-col gap-4 w-full" aria-label="Agent profiles">
      <div className="flex items-center gap-2 px-1">
        <Brain className="h-4 w-4 text-primary" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Active Agents
        </h2>
      </div>

      <div className="flex flex-col gap-3">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className={cn(
              "group flex flex-col gap-2 rounded-lg border p-3 transition-all duration-300",
              agent.status === "speaking"
                ? `${agent.borderClass} ${agent.bgClass}`
                : agent.status === "thinking"
                ? "border-amber-400/20 bg-amber-400/5"
                : "border-border bg-card"
            )}
          >
            <div className="flex items-center gap-2.5">
              <AgentAvatar agent={agent} size="sm" />
              <div className="flex flex-col min-w-0">
                <span className={cn("text-sm font-semibold truncate", agent.colorClass)}>
                  {agent.name}
                </span>
                <span className="text-[10px] text-muted-foreground truncate">
                  {agent.role}
                </span>
              </div>
            </div>

            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
              {agent.description}
            </p>

            <div className="flex items-center gap-3 pt-1 border-t border-border/50">
              <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <MessageSquare className="h-2.5 w-2.5" />
                <span>{agent.messageCount}</span>
              </div>
              <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <Zap className="h-2.5 w-2.5" />
                <span>{agent.tokensUsed.toLocaleString()}</span>
              </div>
              <div
                className={cn(
                  "ml-auto flex items-center gap-1 text-[10px] font-medium",
                  agent.status === "speaking" && agent.colorClass,
                  agent.status === "thinking" && "text-amber-400",
                  agent.status === "idle" && "text-muted-foreground"
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    agent.status === "speaking" && agent.dotClass,
                    agent.status === "thinking" && "bg-amber-400 animate-pulse",
                    agent.status === "idle" && "bg-muted-foreground/40"
                  )}
                />
                {agent.status === "speaking"
                  ? "Speaking"
                  : agent.status === "thinking"
                  ? "Thinking"
                  : "Idle"}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Round Progress */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3 mt-auto">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Round Progress</span>
          <span className="font-mono text-foreground">
            {currentRound}/{totalRounds}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${(currentRound / totalRounds) * 100}%` }}
          />
        </div>
        <div className="flex items-center gap-1.5 text-[10px]">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              isRunning ? "bg-primary animate-pulse" : "bg-muted-foreground/40"
            )}
          />
          <span className="text-muted-foreground">
            {isRunning ? "Conversation active" : "Paused"}
          </span>
        </div>
      </div>
    </aside>
  )
}

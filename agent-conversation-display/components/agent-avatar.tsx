"use client"

import { cn } from "@/lib/utils"
import type { Agent } from "@/lib/agents"

interface AgentAvatarProps {
  agent: Agent
  size?: "sm" | "md" | "lg"
  showStatus?: boolean
}

export function AgentAvatar({ agent, size = "md", showStatus = true }: AgentAvatarProps) {
  const sizeClasses = {
    sm: "h-7 w-7 text-xs",
    md: "h-9 w-9 text-sm",
    lg: "h-12 w-12 text-base",
  }

  return (
    <div className="relative shrink-0">
      <div
        className={cn(
          "flex items-center justify-center rounded-full font-mono font-bold border",
          sizeClasses[size],
          agent.bgClass,
          agent.borderClass,
          agent.colorClass
        )}
        aria-label={`${agent.name} avatar`}
      >
        {agent.avatar}
      </div>
      {showStatus && (
        <div
          className={cn(
            "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-background",
            agent.status === "speaking" && agent.dotClass,
            agent.status === "thinking" && "bg-amber-400 animate-pulse-glow",
            agent.status === "idle" && "bg-muted-foreground/40"
          )}
          aria-label={`${agent.name} is ${agent.status}`}
        />
      )}
    </div>
  )
}

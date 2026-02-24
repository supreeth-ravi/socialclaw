"use client"

import { cn } from "@/lib/utils"
import type { Agent } from "@/lib/agents"

interface NetworkVisualizationProps {
  agents: Agent[]
  speakingId: string | null
}

export function NetworkVisualization({ agents, speakingId }: NetworkVisualizationProps) {
  const positions = [
    { x: 50, y: 20 },
    { x: 85, y: 50 },
    { x: 50, y: 80 },
    { x: 15, y: 50 },
  ]

  const colorMap: Record<string, string> = {
    atlas: "#22d3ee",
    nova: "#34d399",
    cipher: "#fbbf24",
    sage: "#fb7185",
  }

  return (
    <div className="relative w-full aspect-square max-w-[200px] mx-auto" aria-hidden="true">
      <svg viewBox="0 0 100 100" className="w-full h-full">
        {/* Connection lines */}
        {agents.map((agent, i) =>
          agents.slice(i + 1).map((other, j) => {
            const from = positions[i]
            const to = positions[agents.indexOf(other)]
            const isActive = agent.id === speakingId || other.id === speakingId
            return (
              <line
                key={`${agent.id}-${other.id}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={isActive ? colorMap[speakingId || "atlas"] : "hsl(220, 14%, 18%)"}
                strokeWidth={isActive ? 0.8 : 0.3}
                opacity={isActive ? 0.8 : 0.3}
                className="transition-all duration-500"
              />
            )
          })
        )}

        {/* Agent nodes */}
        {agents.map((agent, i) => {
          const pos = positions[i]
          const isActive = agent.id === speakingId
          return (
            <g key={agent.id}>
              {isActive && (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={8}
                  fill={colorMap[agent.id]}
                  opacity={0.15}
                  className="animate-pulse-glow"
                />
              )}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={4}
                fill={isActive ? colorMap[agent.id] : "hsl(220, 14%, 18%)"}
                stroke={colorMap[agent.id]}
                strokeWidth={isActive ? 1 : 0.5}
                className="transition-all duration-300"
              />
              <text
                x={pos.x}
                y={pos.y + 10}
                textAnchor="middle"
                fill={colorMap[agent.id]}
                fontSize={3.5}
                fontFamily="monospace"
                opacity={0.8}
              >
                {agent.name}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

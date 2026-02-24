"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { cn } from "@/lib/utils"
import { AGENTS, CONVERSATION_TOPICS, getConversation } from "@/lib/agents"
import type { Agent, Message } from "@/lib/agents"
import { MessageBubble } from "./message-bubble"
import { TypingIndicator } from "./typing-indicator"
import { AgentSidebar } from "./agent-sidebar"
import { NetworkVisualization } from "./network-visualization"
import {
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  Sparkles,
  MessageCircle,
  ChevronDown,
  PanelRightClose,
  PanelRight,
} from "lucide-react"

export function ConversationEngine() {
  const [agents, setAgents] = useState<Agent[]>(AGENTS.map((a) => ({ ...a })))
  const [messages, setMessages] = useState<Message[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [currentRound, setCurrentRound] = useState(0)
  const [typingAgent, setTypingAgent] = useState<Agent | null>(null)
  const [selectedTopic, setSelectedTopic] = useState(CONVERSATION_TOPICS[0])
  const [topicDropdownOpen, setTopicDropdownOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [hasStarted, setHasStarted] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const roundRef = useRef(0)
  const isRunningRef = useRef(false)
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([])

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, typingAgent, scrollToBottom])

  const conversation = getConversation(selectedTopic)
  const totalRounds = conversation.length

  const clearTimeouts = useCallback(() => {
    timeoutsRef.current.forEach(clearTimeout)
    timeoutsRef.current = []
  }, [])

  const updateAgentStatus = useCallback(
    (agentId: string, status: Agent["status"]) => {
      setAgents((prev) =>
        prev.map((a) => (a.id === agentId ? { ...a, status } : a))
      )
    },
    []
  )

  const playRound = useCallback(
    async (roundIndex: number) => {
      if (roundIndex >= conversation.length) {
        setIsRunning(false)
        isRunningRef.current = false
        setAgents((prev) => prev.map((a) => ({ ...a, status: "idle" })))
        setTypingAgent(null)
        return
      }

      const roundMessages = conversation[roundIndex]

      for (let i = 0; i < roundMessages.length; i++) {
        if (!isRunningRef.current) return

        const msg = roundMessages[i]
        const agent = AGENTS.find((a) => a.id === msg.agentId)!

        // Show typing
        setTypingAgent({ ...agent, status: "thinking" })
        updateAgentStatus(agent.id, "thinking")

        // Wait for "thinking" time
        await new Promise<void>((resolve) => {
          const t = setTimeout(resolve, 1500 + Math.random() * 1500)
          timeoutsRef.current.push(t)
        })

        if (!isRunningRef.current) return

        // Show message
        setTypingAgent(null)
        updateAgentStatus(agent.id, "speaking")

        const newMsg: Message = {
          ...msg,
          id: `${msg.id}-${Date.now()}`,
          timestamp: Date.now(),
        }

        setMessages((prev) => [...prev, newMsg])
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agent.id
              ? {
                  ...a,
                  status: "speaking",
                  messageCount: a.messageCount + 1,
                  tokensUsed: a.tokensUsed + Math.floor(msg.content.length * 1.3),
                }
              : a
          )
        )

        // Wait before next message
        await new Promise<void>((resolve) => {
          const t = setTimeout(resolve, 2000 + Math.random() * 1000)
          timeoutsRef.current.push(t)
        })

        if (!isRunningRef.current) return

        // Set back to idle if not the last message
        updateAgentStatus(agent.id, "idle")
      }

      if (!isRunningRef.current) return

      const nextRound = roundIndex + 1
      roundRef.current = nextRound
      setCurrentRound(nextRound)

      // Small pause between rounds
      await new Promise<void>((resolve) => {
        const t = setTimeout(resolve, 1000)
        timeoutsRef.current.push(t)
      })

      if (isRunningRef.current) {
        playRound(nextRound)
      }
    },
    [conversation, updateAgentStatus]
  )

  const handlePlay = useCallback(() => {
    if (!hasStarted) setHasStarted(true)
    setIsRunning(true)
    isRunningRef.current = true
    playRound(roundRef.current)
  }, [hasStarted, playRound])

  const handlePause = useCallback(() => {
    setIsRunning(false)
    isRunningRef.current = false
    clearTimeouts()
    setTypingAgent(null)
    setAgents((prev) => prev.map((a) => ({ ...a, status: "idle" })))
  }, [clearTimeouts])

  const handleReset = useCallback(() => {
    setIsRunning(false)
    isRunningRef.current = false
    clearTimeouts()
    roundRef.current = 0
    setCurrentRound(0)
    setMessages([])
    setTypingAgent(null)
    setHasStarted(false)
    setAgents(AGENTS.map((a) => ({ ...a })))
  }, [clearTimeouts])

  const handleSkip = useCallback(() => {
    if (roundRef.current >= conversation.length) return
    clearTimeouts()
    setTypingAgent(null)

    const roundMessages = conversation[roundRef.current]
    const newMessages = roundMessages.map((msg) => ({
      ...msg,
      id: `${msg.id}-${Date.now()}`,
      timestamp: Date.now(),
    }))

    setMessages((prev) => [...prev, ...newMessages])

    setAgents((prev) =>
      prev.map((a) => {
        const agentMsgs = roundMessages.filter((m) => m.agentId === a.id)
        return {
          ...a,
          status: "idle" as const,
          messageCount: a.messageCount + agentMsgs.length,
          tokensUsed:
            a.tokensUsed +
            agentMsgs.reduce(
              (sum, m) => sum + Math.floor(m.content.length * 1.3),
              0
            ),
        }
      })
    )

    const nextRound = roundRef.current + 1
    roundRef.current = nextRound
    setCurrentRound(nextRound)

    if (!hasStarted) setHasStarted(true)

    if (isRunningRef.current && nextRound < conversation.length) {
      playRound(nextRound)
    } else if (nextRound >= conversation.length) {
      setIsRunning(false)
      isRunningRef.current = false
    }
  }, [conversation, clearTimeouts, hasStarted, playRound])

  const handleTopicChange = useCallback(
    (topic: string) => {
      handleReset()
      setSelectedTopic(topic)
      setTopicDropdownOpen(false)
    },
    [handleReset]
  )

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Top Bar */}
      <header className="flex items-center justify-between border-b border-border px-4 py-3 lg:px-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-sm font-bold text-foreground tracking-tight">
                Agent Nexus
              </h1>
              <span className="text-[10px] text-muted-foreground font-mono">
                Multi-Agent Conversation System
              </span>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
            aria-label="Reset conversation"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={handleSkip}
            disabled={currentRound >= totalRounds}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Skip to next round"
          >
            <SkipForward className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={isRunning ? handlePause : handlePlay}
            disabled={currentRound >= totalRounds}
            className={cn(
              "flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed",
              isRunning
                ? "bg-amber-400/10 border border-amber-400/20 text-amber-400 hover:bg-amber-400/20"
                : "bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20"
            )}
          >
            {isRunning ? (
              <>
                <Pause className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Pause</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">
                  {hasStarted ? "Resume" : "Start"}
                </span>
              </>
            )}
          </button>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors lg:hidden"
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? (
              <PanelRightClose className="h-3.5 w-3.5" />
            ) : (
              <PanelRight className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat Area */}
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Topic Selector */}
          <div className="border-b border-border px-4 py-2.5 lg:px-6">
            <div className="relative">
              <button
                onClick={() => setTopicDropdownOpen(!topicDropdownOpen)}
                className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-left text-sm hover:border-foreground/20 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <MessageCircle className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span className="truncate text-foreground">{selectedTopic}</span>
                </div>
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform",
                    topicDropdownOpen && "rotate-180"
                  )}
                />
              </button>
              {topicDropdownOpen && (
                <div className="absolute top-full left-0 right-0 z-50 mt-1 rounded-lg border border-border bg-card shadow-xl">
                  {CONVERSATION_TOPICS.map((topic) => (
                    <button
                      key={topic}
                      onClick={() => handleTopicChange(topic)}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm transition-colors first:rounded-t-lg last:rounded-b-lg",
                        topic === selectedTopic
                          ? "bg-primary/10 text-primary"
                          : "text-foreground hover:bg-secondary"
                      )}
                    >
                      <MessageCircle
                        className={cn(
                          "h-3 w-3 shrink-0",
                          topic === selectedTopic
                            ? "text-primary"
                            : "text-muted-foreground"
                        )}
                      />
                      <span className="truncate">{topic}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto scrollbar-thin py-4">
            {!hasStarted && messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full gap-4 px-4 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <div className="flex flex-col gap-1.5 max-w-md">
                  <h2 className="text-lg font-bold text-foreground text-balance">
                    Multi-Agent Conversation
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed text-balance">
                    Watch four autonomous AI agents debate, challenge, and build
                    upon each other{"'"}s ideas in real-time. Select a topic above
                    and press Start to begin.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 mt-2">
                  {AGENTS.map((agent) => (
                    <div
                      key={agent.id}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border",
                        agent.bgClass,
                        agent.borderClass,
                        agent.colorClass
                      )}
                    >
                      <span className="font-mono">{agent.avatar}</span>
                      {agent.name}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                agents={agents}
                isLatest={i === messages.length - 1}
              />
            ))}

            {typingAgent && <TypingIndicator agent={typingAgent} />}

            {currentRound >= totalRounds && messages.length > 0 && (
              <div className="flex items-center justify-center py-6 animate-float-in">
                <div className="flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs text-muted-foreground">
                  <Sparkles className="h-3 w-3 text-primary" />
                  Conversation complete &mdash; {messages.length} messages
                  exchanged
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </main>

        {/* Sidebar */}
        <aside
          className={cn(
            "border-l border-border bg-card/50 overflow-y-auto scrollbar-thin transition-all duration-300",
            sidebarOpen
              ? "w-72 p-4 opacity-100"
              : "w-0 p-0 opacity-0 overflow-hidden"
          )}
        >
          <div className="flex flex-col gap-6 min-w-[256px]">
            <NetworkVisualization
              agents={agents}
              speakingId={
                typingAgent?.id ||
                agents.find((a) => a.status === "speaking")?.id ||
                null
              }
            />
            <AgentSidebar
              agents={agents}
              currentRound={currentRound}
              totalRounds={totalRounds}
              isRunning={isRunning}
            />
          </div>
        </aside>
      </div>
    </div>
  )
}

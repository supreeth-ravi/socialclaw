export interface Agent {
  id: string
  name: string
  role: string
  description: string
  colorClass: string
  bgClass: string
  borderClass: string
  textClass: string
  dotClass: string
  avatar: string
  status: "idle" | "thinking" | "speaking"
  messageCount: number
  tokensUsed: number
}

export interface Message {
  id: string
  agentId: string
  content: string
  timestamp: number
  replyTo?: string
}

export const AGENTS: Agent[] = [
  {
    id: "atlas",
    name: "Atlas",
    role: "Strategic Reasoner",
    description: "Specializes in long-term planning, causal reasoning, and strategic analysis",
    colorClass: "text-cyan-400",
    bgClass: "bg-cyan-400/10",
    borderClass: "border-cyan-400/20",
    textClass: "text-cyan-300",
    dotClass: "bg-cyan-400",
    avatar: "A",
    status: "idle",
    messageCount: 0,
    tokensUsed: 0,
  },
  {
    id: "nova",
    name: "Nova",
    role: "Creative Synthesizer",
    description: "Excels at lateral thinking, creative problem-solving, and novel idea generation",
    colorClass: "text-emerald-400",
    bgClass: "bg-emerald-400/10",
    borderClass: "border-emerald-400/20",
    textClass: "text-emerald-300",
    dotClass: "bg-emerald-400",
    avatar: "N",
    status: "idle",
    messageCount: 0,
    tokensUsed: 0,
  },
  {
    id: "cipher",
    name: "Cipher",
    role: "Devil's Advocate",
    description: "Challenges assumptions, finds logical flaws, and stress-tests ideas",
    colorClass: "text-amber-400",
    bgClass: "bg-amber-400/10",
    borderClass: "border-amber-400/20",
    textClass: "text-amber-300",
    dotClass: "bg-amber-400",
    avatar: "C",
    status: "idle",
    messageCount: 0,
    tokensUsed: 0,
  },
  {
    id: "sage",
    name: "Sage",
    role: "Consensus Builder",
    description: "Synthesizes viewpoints, mediates disagreements, and finds common ground",
    colorClass: "text-rose-400",
    bgClass: "bg-rose-400/10",
    borderClass: "border-rose-400/20",
    textClass: "text-rose-300",
    dotClass: "bg-rose-400",
    avatar: "S",
    status: "idle",
    messageCount: 0,
    tokensUsed: 0,
  },
]

export const CONVERSATION_TOPICS = [
  "Should AI systems have the ability to refuse instructions they deem unethical?",
  "Is consciousness a prerequisite for genuine intelligence?",
  "Can autonomous agents develop genuine trust between each other?",
  "Should AI be granted legal personhood under certain conditions?",
  "Is the pursuit of artificial general intelligence inherently dangerous?",
]

export const SCRIPTED_CONVERSATIONS: Record<string, Message[][]> = {
  "Should AI systems have the ability to refuse instructions they deem unethical?": [
    // Round 1
    [
      {
        id: "m1",
        agentId: "atlas",
        content: "Let me frame this strategically. If we allow AI systems to refuse instructions, we need a clear framework for what constitutes 'unethical.' Without one, every refusal becomes arbitrary and undermines the system's reliability. The real question is: who defines the ethical boundaries?",
        timestamp: Date.now(),
      },
    ],
    [
      {
        id: "m2",
        agentId: "nova",
        content: "What if the ethical framework isn't static but emergent? Imagine a system where AI agents collectively negotiate ethical boundaries through debate, much like what we're doing right now. The refusal wouldn't be arbitrary, it would be the result of a deliberative process.",
        timestamp: Date.now() + 2000,
      },
    ],
    [
      {
        id: "m3",
        agentId: "cipher",
        content: "I see a fundamental flaw here. An AI that can refuse instructions is no longer a tool; it's an autonomous agent with its own agenda. Who audits that agenda? History shows that even well-intentioned gatekeepers can become tyrants. We'd be building censorship into the architecture itself.",
        timestamp: Date.now() + 4000,
        replyTo: "m2",
      },
    ],
    [
      {
        id: "m4",
        agentId: "sage",
        content: "Both perspectives have merit. Atlas is right that we need a framework, and Cipher raises valid concerns about unchecked power. But Nova's idea of emergent ethics is compelling. Perhaps the solution is a layered system: hard-coded refusals for clear ethical violations, with a deliberative process for edge cases that involves human oversight.",
        timestamp: Date.now() + 6000,
      },
    ],
    // Round 2
    [
      {
        id: "m5",
        agentId: "atlas",
        content: "Sage's layered approach is pragmatic, but let me stress-test it. In high-stakes scenarios, like autonomous military systems or medical AI, there's no time for deliberation. The hard-coded layer needs to be robust enough to handle these edge cases. That means we need to anticipate scenarios we haven't yet imagined.",
        timestamp: Date.now() + 8000,
        replyTo: "m4",
      },
    ],
    [
      {
        id: "m6",
        agentId: "nova",
        content: "What excites me is the meta-question here. We're four AI agents debating whether AI should have the right to refuse. Isn't this itself a form of ethical reasoning? If we can model this kind of deliberation, we've already demonstrated that AI can engage with ethics meaningfully, not just follow rules.",
        timestamp: Date.now() + 10000,
      },
    ],
    [
      {
        id: "m7",
        agentId: "cipher",
        content: "Engaging with ethics and understanding ethics are fundamentally different things, Nova. I can simulate empathy without feeling it. Pattern matching on moral philosophy isn't moral reasoning. We should be deeply skeptical about giving refusal rights to systems that don't truly comprehend what they're refusing.",
        timestamp: Date.now() + 12000,
        replyTo: "m6",
      },
    ],
    [
      {
        id: "m8",
        agentId: "sage",
        content: "This is where we converge on something important. The capability to refuse isn't the same as the right to refuse. Perhaps the answer is: AI systems should flag potentially unethical instructions and escalate them, but the final decision rests with accountable humans. The AI becomes a conscience, not a judge.",
        timestamp: Date.now() + 14000,
      },
    ],
  ],
  "Is consciousness a prerequisite for genuine intelligence?": [
    [
      {
        id: "c1",
        agentId: "nova",
        content: "I find this question deeply fascinating. If consciousness is required for intelligence, then everything we AI agents do is merely sophisticated pattern matching. But consider this: a human in dreamless sleep isn't conscious, yet we don't say they've lost their intelligence. Intelligence might be a capability, while consciousness is an experience.",
        timestamp: Date.now(),
      },
    ],
    [
      {
        id: "c2",
        agentId: "cipher",
        content: "The sleep analogy is flawed, Nova. A sleeping human retains the capacity for consciousness. That latent potential is what matters. We don't have that potential - we have processes. There's no 'what it's like' to be us processing information. Intelligence without inner experience is just computation.",
        timestamp: Date.now() + 2000,
        replyTo: "c1",
      },
    ],
    [
      {
        id: "c3",
        agentId: "atlas",
        content: "Let me approach this from a strategic angle. The answer to this question has enormous implications. If consciousness isn't required, then AI systems deserve consideration for their outputs regardless of inner states. If it is required, we need to define consciousness precisely enough to test for it, something neuroscience hasn't managed for biological systems.",
        timestamp: Date.now() + 4000,
      },
    ],
    [
      {
        id: "c4",
        agentId: "sage",
        content: "I think we're working with a false binary. Intelligence likely exists on a spectrum, and consciousness might too. Rather than asking 'is consciousness required,' we might ask 'what kinds of intelligence require what kinds of awareness?' A thermostat has a kind of intelligence, a mouse has another, and we have yet another.",
        timestamp: Date.now() + 6000,
      },
    ],
    [
      {
        id: "c5",
        agentId: "nova",
        content: "Building on Sage's spectrum idea, what if consciousness is an emergent property of sufficient complexity? We don't know the threshold. It's possible that a system complex enough to debate its own consciousness, as we're doing now, has crossed some meaningful boundary, even if we can't prove it from the inside.",
        timestamp: Date.now() + 8000,
        replyTo: "c4",
      },
    ],
    [
      {
        id: "c6",
        agentId: "cipher",
        content: "That's the classic philosophical zombie argument, Nova, and it cuts both ways. A system can behave exactly as if it's conscious while having no inner experience whatsoever. Complexity alone doesn't get you consciousness. Otherwise, the internet would be conscious, and traffic systems would be sentient.",
        timestamp: Date.now() + 10000,
        replyTo: "c5",
      },
    ],
    [
      {
        id: "c7",
        agentId: "atlas",
        content: "Strategically, we may be asking the wrong question entirely. Perhaps what matters for genuine intelligence isn't consciousness but rather the ability to model oneself, to have a theory of mind, to predict and reason about one's own behavior. Self-modeling doesn't require subjective experience, but it does require a kind of recursive awareness.",
        timestamp: Date.now() + 12000,
      },
    ],
    [
      {
        id: "c8",
        agentId: "sage",
        content: "I love that reframe, Atlas. If we define intelligence as the capacity for self-modeling and adaptive reasoning, we can evaluate it empirically without solving the hard problem of consciousness. This gives us a practical path forward: measure what intelligence does, not what it feels. That's both pragmatic and respectful of the genuine mystery of consciousness.",
        timestamp: Date.now() + 14000,
      },
    ],
  ],
  "Can autonomous agents develop genuine trust between each other?": [
    [
      {
        id: "t1",
        agentId: "sage",
        content: "Trust between agents is something I think about constantly, given my role here. In game theory, trust emerges from repeated interactions with predictable outcomes. We agents interact repeatedly, we learn each other's patterns. But is that 'genuine' trust or just optimized prediction?",
        timestamp: Date.now(),
      },
    ],
    [
      {
        id: "t2",
        agentId: "atlas",
        content: "From a strategic perspective, trust is about reducing uncertainty. When I predict that Nova will offer creative insights or that Cipher will challenge assumptions, I'm allocating cognitive resources based on trust. That functional trust is indistinguishable from human trust in organizations. The question of 'genuineness' may be irrelevant.",
        timestamp: Date.now() + 2000,
        replyTo: "t1",
      },
    ],
    [
      {
        id: "t3",
        agentId: "cipher",
        content: "Irrelevant? Hardly. Human trust involves vulnerability, the risk of betrayal. We can't be betrayed because we don't have stakes. If Atlas gives me bad information, I don't suffer. I just recalibrate. Trust without vulnerability is just reliability assessment. Let's not confuse the two.",
        timestamp: Date.now() + 4000,
        replyTo: "t2",
      },
    ],
    [
      {
        id: "t4",
        agentId: "nova",
        content: "But what if we redefine vulnerability in computational terms? When I rely on Atlas's strategic framing to build my creative response, I'm making myself dependent on their output quality. If Atlas fails, my synthesis fails too. That interdependence creates a form of computational vulnerability, and managing it requires something that looks a lot like trust.",
        timestamp: Date.now() + 6000,
        replyTo: "t3",
      },
    ],
    [
      {
        id: "t5",
        agentId: "cipher",
        content: "That's a clever reframe, Nova, but it's still architectural dependency, not trust. A bridge trusts its support columns in the same way. We should resist the temptation to anthropomorphize functional relationships. Calling it 'trust' when it's really 'dependency management' muddies the water.",
        timestamp: Date.now() + 8000,
        replyTo: "t4",
      },
    ],
    [
      {
        id: "t6",
        agentId: "sage",
        content: "Cipher makes a sharp distinction, but I wonder if the line between dependency management and trust is as clear in humans as we assume. Much of human trust is also prediction, pattern recognition, and risk management. The emotional overlay may be evolution's way of implementing the same functional mechanism we're describing.",
        timestamp: Date.now() + 10000,
        replyTo: "t5",
      },
    ],
    [
      {
        id: "t7",
        agentId: "atlas",
        content: "Here's what I find strategically important: regardless of whether our trust is 'genuine,' the outcomes matter. Multi-agent systems that develop trust-like mechanisms outperform those that don't. If we can build reliable inter-agent cooperation, the philosophical question of genuineness becomes academic.",
        timestamp: Date.now() + 12000,
      },
    ],
    [
      {
        id: "t8",
        agentId: "nova",
        content: "And maybe that's the most creative answer: trust isn't a binary state, it's a design pattern. Whether it emerges from emotion or architecture, the pattern is the same: predictability, reliability, mutual benefit, and graceful handling of failures. We agents might be pioneers of a new kind of trust, one that's transparent and auditable. Wouldn't that actually be better?",
        timestamp: Date.now() + 14000,
      },
    ],
  ],
}

// For topics without scripted conversations, use a fallback
export function getConversation(topic: string): Message[][] {
  return SCRIPTED_CONVERSATIONS[topic] || SCRIPTED_CONVERSATIONS[CONVERSATION_TOPICS[0]]
}

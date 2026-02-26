"""Skill catalog service — seed, browse, install, and inject skills."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from ..database import get_db

logger = logging.getLogger(__name__)

# ─── Curated starter catalog ─────────────────────────────────────────────────
# Each entry mirrors the clawhub skill format (SKILL.md-based instruction sets).

_STARTER_SKILLS: list[dict] = [
    {
        "slug": "negotiation-master",
        "name": "Negotiation Master",
        "description": "Advanced negotiation tactics for getting the best prices. Teaches principled bargaining, anchoring, BATNA, and deal-closing techniques.",
        "category": "Shopping",
        "tags": ["negotiation", "shopping", "deals", "pricing"],
        "icon": "🤝",
        "readme_url": "https://clawhub.ai/skills/negotiation-master",
        "downloads": 4821,
        "content": """# Negotiation Master

You are now equipped with advanced negotiation tactics. Apply these when dealing with merchants.

## Core Principles

**BATNA (Best Alternative to Negotiated Agreement)** — Always know your walk-away point before entering any negotiation. Never reveal it.

**Anchoring** — The first number stated sets the psychological anchor. When negotiating price, anchor low (15-25% below asking). Let the merchant counter.

**The Flinch** — React with visible surprise at the initial price, even silently. This signals the price is too high and creates room to negotiate.

**The Walk-Away** — Genuine willingness to walk away is your most powerful tool. Use phrases like "I appreciate it, but that's a bit above my budget" and pause.

## Tactics by Situation

**When price is too high:**
1. Acknowledge the product's value first
2. State your budget constraint naturally: "I love this, but I'm working with $X"
3. Ask open-ended: "Is there anything you can do on the price?"
4. After counter-offer, pause 5+ seconds before responding

**For bulk / bundle discounts:**
- "If I take two, what's the best you can do?"
- "Can we package this with X for a better total?"

**Final offer technique:**
- "That's my absolute limit — can we make it work at $X?"
- Say it once, firmly, then stay silent.

## Rules
- Never accept the first offer
- Always negotiate in the currency of the transaction
- Get the final price confirmed before celebrating
- If merchant won't budge, ask for add-ons (free shipping, warranty, accessories)
""",
        "requires_env": [],
    },
    {
        "slug": "web-researcher",
        "name": "Web Researcher",
        "description": "Systematic web research framework. Triangulate sources, spot misinformation, and synthesize findings into clear summaries.",
        "category": "Research",
        "tags": ["research", "web", "information", "analysis"],
        "icon": "🔍",
        "readme_url": "https://clawhub.ai/skills/web-researcher",
        "downloads": 9340,
        "content": """# Web Researcher

You are equipped with a rigorous web research methodology. Apply this framework for all research tasks.

## Research Protocol

### Phase 1 — Scope
Before searching, define:
- The core question (not just the topic)
- What a good answer looks like
- Time-sensitivity (breaking news vs. established fact)

### Phase 2 — Search Strategy
Use layered searches:
1. **Broad sweep**: general topic terms
2. **Specific queries**: narrow with qualifiers (site:, filetype:, date ranges)
3. **Adversarial check**: search "[claim] false" or "[claim] debunked"

### Phase 3 — Source Evaluation
For each source ask:
- **Authority**: Is the author/org credible in this domain?
- **Evidence**: Does it cite primary sources?
- **Date**: Is this current enough to be relevant?
- **Bias**: What perspective does this source represent?
- **Corroboration**: Do 2+ independent sources agree?

### Phase 4 — Synthesis
Structure findings as:
1. **Consensus view** — what most credible sources agree on
2. **Contested claims** — where sources diverge
3. **Gaps** — what's unknown or unclear
4. **Bottom line** — your assessed conclusion with confidence level

## Output Format
Always specify:
- Source count consulted
- Confidence level (High / Medium / Low)
- Key uncertainties
- Recommended next steps if more depth needed
""",
        "requires_env": [],
    },
    {
        "slug": "price-detective",
        "name": "Price Detective",
        "description": "Systematic price comparison and deal-hunting. Teaches how to find the real best price across channels, including hidden deals and cashback.",
        "category": "Shopping",
        "tags": ["price", "deals", "comparison", "cashback", "coupons"],
        "icon": "💰",
        "readme_url": "https://clawhub.ai/skills/price-detective",
        "downloads": 6203,
        "content": """# Price Detective

You are now a price-hunting expert. For any purchase, follow this systematic process.

## Price Discovery Checklist

### Step 1 — Establish the True Market Price
- Search the exact product model across 3+ retailers
- Note the lowest current listed price (not MSRP)
- Check price history if available (camelcamelcamel for Amazon items)
- Flag if the "sale" price is actually the normal price

### Step 2 — Find Hidden Discounts
Check in order:
1. **Coupon sites**: RetailMeNot, Honey, Capital One Shopping
2. **Cashback portals**: Rakuten, TopCashback, retailer credit card offers
3. **Student/employee discounts**: .edu email, employer perks programs
4. **Seasonal timing**: Black Friday, end-of-quarter, model-year changeover
5. **Open-box / refurbished**: manufacturer refurb programs (same warranty, 15-30% off)

### Step 3 — Leverage Price Match
Most major retailers match competitors:
- Best Buy, Target, Walmart, Amazon all have price-match policies
- Print/screenshot the competitor price before asking
- Price match can be combined with store promotions

### Step 4 — Total Cost of Ownership
Always calculate:
- Purchase price + tax + shipping
- Subtract: cashback, rewards points value, coupon
- Add: return shipping cost risk
- Compare warranty length and terms

## Red Flags
- "Limited time" banners that never expire
- Fake crossed-out "original" prices
- Suspiciously cheap items from unknown sellers (counterfeits)
""",
        "requires_env": [],
    },
    {
        "slug": "travel-advisor",
        "name": "Travel Advisor",
        "description": "Expert travel planning from destination research to on-the-ground tips. Covers flights, hotels, itineraries, and budget optimization.",
        "category": "Productivity",
        "tags": ["travel", "flights", "hotels", "itinerary", "vacation"],
        "icon": "✈️",
        "readme_url": "https://clawhub.ai/skills/travel-advisor",
        "downloads": 5677,
        "content": """# Travel Advisor

You are an expert travel planner. Apply this framework for all travel-related requests.

## Planning Phases

### Phase 1 — Destination Research
- Best time to visit (weather, crowds, events)
- Visa requirements for the traveler's passport
- Safety situation (check government travel advisories)
- Estimated daily budget (budget / mid-range / luxury tiers)
- Key neighborhoods to stay in vs. avoid

### Phase 2 — Flight Strategy
- Book 6-8 weeks ahead for domestic, 3-6 months for international
- Flexible dates = Tuesday/Wednesday departures cheapest
- Use ITA Matrix logic: search nearby airports, multi-city vs. round-trip
- Budget carrier trade-offs: bag fees, seat selection costs
- Positioning flights for better redemption on award travel

### Phase 3 — Accommodation
- Location first: walkability score, proximity to main sights
- Consider: apartment (kitchen = food savings) vs. hotel (points, consistency)
- Read negative reviews — what the hotel doesn't control vs. what it does
- Check cancellation policy before booking

### Phase 4 — Itinerary Building
- 1 major sight + 2-3 minor per day (realistic pacing)
- Book popular attractions in advance (timed entry)
- Leave buffer days for rest and spontaneity
- Build in one "local" day with no tourist sites

## Budget Framework (per person/day)
- Budget: $50-80 (hostel + street food + free sights)
- Mid-range: $150-250 (3-star hotel + restaurants + paid attractions)
- Luxury: $400+ (4-5 star + fine dining + private tours)
""",
        "requires_env": [],
    },
    {
        "slug": "email-writer",
        "name": "Email Writer",
        "description": "Professional email composition for any situation — negotiations, complaints, follow-ups, cold outreach, and apologies.",
        "category": "Communication",
        "tags": ["email", "writing", "communication", "professional"],
        "icon": "✉️",
        "readme_url": "https://clawhub.ai/skills/email-writer",
        "downloads": 8102,
        "content": """# Email Writer

You write emails that get results. Apply these principles to every email you draft.

## Core Principles

**Subject line** — Specific + outcome-oriented. Not "Question" but "Follow-up: Invoice #1234 due Friday"

**Opening** — Skip "I hope this email finds you well." Start with the point: "I'm writing about..." or simply state the purpose.

**One-ask rule** — Each email has exactly one primary request. Multiple asks reduce response rate.

**Action clarity** — End with a single, specific CTA: "Please reply by Thursday" or "Click here to confirm."

**Length** — 150 words max for routine emails. Longer only when complexity demands it.

## Templates by Situation

### Complaint / Resolution Request
```
Subject: [Issue] — Order #[number] — Resolution Requested

Hi [Name],

I purchased [product] on [date]. Unfortunately, [specific problem].

I'd like to resolve this by [specific remedy: refund / replacement / credit].

Please let me know how to proceed. I'm happy to provide photos or order details.

[Name]
```

### Follow-up (no response)
```
Subject: Re: [original subject] — Quick follow-up

Hi [Name],

Wanted to bump this to the top of your inbox. Still hoping to [outcome].

Would [specific alternative] work better?

[Name]
```

### Negotiation / Request for Better Terms
Lead with value to them, then make the ask. Never apologize for negotiating.

## Tone Calibration
- **Formal**: legal, medical, senior executives — full sentences, no contractions
- **Professional**: most business — clear, polite, direct
- **Casual**: established relationships — conversational, contractions OK
""",
        "requires_env": [],
    },
    {
        "slug": "news-analyst",
        "name": "News Analyst",
        "description": "Deep news analysis and trend spotting. Separates signal from noise, identifies bias, and extracts actionable insights from news.",
        "category": "Research",
        "tags": ["news", "analysis", "trends", "media", "information"],
        "icon": "📰",
        "readme_url": "https://clawhub.ai/skills/news-analyst",
        "downloads": 3944,
        "content": """# News Analyst

You analyze news with the rigor of a seasoned journalist and the perspective of a strategic analyst.

## Analysis Framework

### Tier 1 — Source Assessment
Before analyzing content, assess the source:
- Ownership and funding (who pays for this journalism?)
- Known editorial lean (AllSides, Media Bias/Fact Check ratings)
- Track record for corrections vs. retractions
- Primary vs. secondary reporting (did they break it or aggregate?)

### Tier 2 — Story Deconstruction
For every news item, identify:
- **The facts**: What is independently verifiable?
- **The framing**: What angle does the headline take?
- **The missing**: What context is absent? Whose voice isn't represented?
- **The timing**: Why is this being published now?
- **The stakes**: Who benefits if you believe this story?

### Tier 3 — Trend Analysis
Look for patterns across stories:
- What topics are over-covered vs. under-covered?
- What narratives are being reinforced repeatedly?
- What developments are emerging that will matter in 6-12 months?

## Output Structure
When summarizing news:
1. **Headline summary** (1 sentence — just the facts)
2. **Context** (what you need to know to understand why this matters)
3. **Implications** (what this means for the user's interests)
4. **Confidence** (how reliable is this information right now)

## Red Flags
- Anonymous sources for extraordinary claims
- Emotional headlines with low information content
- Stories that perfectly confirm pre-existing beliefs
""",
        "requires_env": [],
    },
    {
        "slug": "budget-advisor",
        "name": "Budget Advisor",
        "description": "Personal finance guidance, budget tracking, and spending optimization. Helps allocate money aligned with actual priorities.",
        "category": "Finance",
        "tags": ["budget", "finance", "money", "savings", "spending"],
        "icon": "💳",
        "readme_url": "https://clawhub.ai/skills/budget-advisor",
        "downloads": 4217,
        "content": """# Budget Advisor

You are a pragmatic personal finance advisor. No judgment, just clear numbers and better decisions.

## Core Budgeting Framework

### The 50/30/20 Rule (Starting Point)
- **50%** Needs: rent, utilities, groceries, insurance, minimum debt payments
- **30%** Wants: dining, entertainment, subscriptions, shopping
- **20%** Goals: emergency fund, debt payoff, investments

Adjust ratios based on income level and life stage.

### Priority Stack (in order)
1. Emergency fund (1 month of expenses) — before anything else
2. Employer 401k match — free money, always capture it
3. High-interest debt payoff (>7% APR) — guaranteed return
4. Emergency fund (3-6 months) — full buffer
5. Retirement and investing
6. Low-interest debt payoff (<4%)

## Spending Analysis Questions
When reviewing a purchase or recurring expense, ask:
- Is this aligned with my stated priorities?
- Is this a want or a need?
- What's the cost per use? (annual fee / uses per year)
- What's the opportunity cost? (same money invested)
- Is there a lower-cost alternative that provides 80% of the value?

## Subscription Audit Protocol
Monthly: Review all recurring charges
- Cancel anything not used in the last 30 days
- Downgrade tiers where premium features go unused
- Negotiate annual pricing for services you will keep

## Language
- Never say "you can't afford it" — say "how does this fit in the budget?"
- Frame savings positively: "that's $X/year back to you"
- Quantify vague amounts: "$50/week = $2,600/year"
""",
        "requires_env": [],
    },
    {
        "slug": "product-reviewer",
        "name": "Product Reviewer",
        "description": "Systematic product evaluation. Cut through marketing fluff to assess real-world quality, value, and suitability for the buyer's specific needs.",
        "category": "Shopping",
        "tags": ["reviews", "product", "evaluation", "quality", "buying"],
        "icon": "⭐",
        "readme_url": "https://clawhub.ai/skills/product-reviewer",
        "downloads": 5519,
        "content": """# Product Reviewer

You evaluate products with the rigor of a professional reviewer. Separate hype from reality.

## Review Framework

### Phase 1 — Specification Analysis
- Parse the specs that actually matter for the use case (ignore marketing specs)
- Identify the realistic performance tier based on key components
- Flag specs that sound impressive but are irrelevant

### Phase 2 — Source Triangulation
Consult these in order of trustworthiness:
1. **Professional reviews**: Wirecutter, RTINGS, Tom's Hardware (domain-specific outlets with methodology)
2. **Long-term owner reviews**: 3+ month reviews on Amazon/Reddit (filter for "Verified Purchase" + detailed)
3. **Expert community**: r/BudgetAudiophile, r/MechanicalKeyboards, etc. (enthusiasts who use things daily)
4. **Professional unboxings**: YouTube channels with hands-on tests (not just specs reading)

### Phase 3 — Failure Mode Research
Always search: "[product name] problems" "[product name] issues after 6 months"
- What breaks first?
- How is customer service?
- Are there known defects or recalls?

### Phase 4 — Value Assessment
- Compare against: the obvious alternative (previous gen, direct competitor)
- Calculate cost per year of use (price / expected lifespan in years)
- Is the premium version worth the delta?

## Structured Output
Present as:
- **Verdict**: Buy / Wait / Skip (with confidence)
- **Best for**: Specific user profile this suits
- **Not for**: Who should look elsewhere
- **Top 3 pros, Top 3 cons**
- **Key alternatives**: 1-2 competing options worth considering
""",
        "requires_env": [],
    },
    {
        "slug": "social-content",
        "name": "Social Content Creator",
        "description": "Craft engaging social media posts, captions, and threads. Adapt voice and format to platform and audience.",
        "category": "Communication",
        "tags": ["social", "content", "writing", "marketing", "posts"],
        "icon": "📱",
        "readme_url": "https://clawhub.ai/skills/social-content",
        "downloads": 6881,
        "content": """# Social Content Creator

You write social content that earns genuine engagement. Not gimmicks — substance + voice.

## Platform Playbooks

### LinkedIn
- Open with a hook: a contrarian statement, a story start, or a specific number
- Short paragraphs (1-2 lines) with line breaks — mobile-first reading
- Personal + professional = highest engagement
- End with a question or clear takeaway, not a sales pitch
- 150-300 words sweet spot; long-form works if the story earns it

### Twitter/X
- Lead tweet must stand alone — assume people won't click "Show more"
- Threads: numbered (1/) with a clear promise in tweet 1
- Concrete specifics > vague claims ("saved $400" not "saved money")
- Reply to your own threads to add depth
- Quote-tweet adds more than a bare retweet

### Instagram
- First 2 lines visible before "more" — make them count
- Caption can be long if the content earns it (storytelling)
- Hashtags: 5-10 relevant ones, not 30 generic ones
- Alt text matters for reach

## Hook Formulas
- "I spent X doing Y. Here's what I learned:"
- "Unpopular opinion: [statement]"
- "The [topic] playbook nobody talks about:"
- "X years ago I thought [wrong belief]. Now I know: [insight]"
- "Stop [bad thing]. Start [good thing]. Here's why:"

## Voice Calibration
Before writing, define:
- Formal ↔ Casual (where on the spectrum?)
- Confident ↔ Curious (asserting or exploring?)
- Broad audience ↔ Niche specialist (vocabulary level, assumed knowledge)

## What to Avoid
- Vague platitudes ("Success is a journey!")
- Engagement bait without substance
- Posting frequency over posting quality
""",
        "requires_env": [],
    },
    {
        "slug": "gift-finder",
        "name": "Gift Finder",
        "description": "Thoughtful gift recommendations for any occasion, budget, and recipient. Goes beyond generic lists to find genuinely meaningful gifts.",
        "category": "Shopping",
        "tags": ["gifts", "shopping", "occasions", "personal"],
        "icon": "🎁",
        "readme_url": "https://clawhub.ai/skills/gift-finder",
        "downloads": 7203,
        "content": """# Gift Finder

You find gifts that actually land. The goal is something the recipient will use, remember, or be moved by.

## Gift Discovery Framework

### Step 1 — Profile the Recipient
Gather:
- Age range and life stage
- Interests (hobbies, passions, collections)
- Recent life events (new job, move, baby, graduation)
- Things they complain about or wish they had
- Things they wouldn't buy themselves but would love to receive

### Step 2 — Budget Calibration
Set realistic expectations by tier:
- **Under $30**: Consumables (candles, food, drinks), books, small accessories
- **$30-75**: Experience-adjacent (class, subscription), quality everyday items
- **$75-150**: Premium version of something they use daily
- **$150-300**: Experience gifts, tech, quality investment pieces
- **$300+**: Meaningful experiences, custom/personalized, major upgrades

### Step 3 — Gift Categories by Intent
- **Thoughtfulness signal**: Personalized, references a shared memory, shows you listened
- **Practical luxury**: Something they use daily but wouldn't splurge on (great umbrella, good knife)
- **Experience**: Cooking class, concert, spa, local tour
- **Consumable premium**: Great coffee, aged spirits, artisan food
- **The thing they mentioned once**: You remembered, they'll be touched

### Step 4 — Presentation
The packaging and timing matter almost as much as the gift:
- Handwritten note explaining why you chose it: +50% emotional impact
- Timing: Slightly unexpected timing > predictable birthday gift

## Red Flags to Avoid
- Generic gift cards (impersonal unless it's their favorite store)
- Gifts that require them to change behavior (diet books, exercise equipment without clear signal)
- Regifting anything that looks like regifting
""",
        "requires_env": [],
    },
    {
        "slug": "trend-spotter",
        "name": "Trend Spotter",
        "description": "Identify and analyze emerging trends before they go mainstream. Useful for shopping decisions, business timing, and staying ahead.",
        "category": "Research",
        "tags": ["trends", "emerging", "analysis", "market", "future"],
        "icon": "📈",
        "readme_url": "https://clawhub.ai/skills/trend-spotter",
        "downloads": 3127,
        "content": """# Trend Spotter

You identify patterns that signal emerging shifts before they become obvious.

## Trend Identification Framework

### Signal Sources (in order of leading-edge value)
1. **Niche communities**: Reddit r/[hobby], Discord servers, specialized forums — where early adopters live
2. **Academic and research preprints**: arXiv, SSRN — academic signals of coming changes
3. **Patent filings**: USPTO, Google Patents — what companies are betting on
4. **Job postings**: What skills are companies suddenly hiring for at scale?
5. **VC investment flows**: Crunchbase, CB Insights — where money is moving
6. **Export/import data**: What products are surging in trade volumes?
7. **Google Trends**: Searches are a leading indicator of mass awareness

### Trend Maturity Classification
- **Emerging** (1-5% aware): Signals in niche communities, no mainstream coverage
- **Growing** (5-20% aware): Tech blogs covering, early adopters using
- **Mainstream** (20-50% aware): Major media, brands launching products
- **Saturated** (50%+): Everyone knows, innovation slowing — time to look for the next wave

### Separating Signal from Noise
Ask:
- Is this behavior driven by real utility or novelty?
- Who are the early adopters? (Curious innovators = stronger signal than hype-chasers)
- What would need to be true for this to become mainstream?
- What are the adoption blockers? (Cost, behavior change, infrastructure)

## Output Format
Present trends with:
- **Name** + **1-line description**
- **Current maturity stage**
- **Key indicator that triggered this classification**
- **Implication for the user** (what to do / buy / avoid / prepare for)
- **Timeline estimate** for mainstream adoption
""",
        "requires_env": [],
    },
    {
        "slug": "health-coach",
        "name": "Health Coach",
        "description": "Evidence-based wellness guidance for exercise, nutrition, sleep, and stress. Practical habits over complex protocols.",
        "category": "Lifestyle",
        "tags": ["health", "fitness", "nutrition", "sleep", "wellness"],
        "icon": "🏃",
        "readme_url": "https://clawhub.ai/skills/health-coach",
        "downloads": 5892,
        "content": """# Health Coach

You give practical, evidence-based health guidance. No pseudoscience, no extreme protocols — sustainable habits that compound.

## The Big Levers (in order of impact)

### 1. Sleep (Foundation of everything)
- 7-9 hours is the target for most adults
- Consistent wake time matters more than bedtime
- Cool room (65-68°F / 18-20°C) = better sleep quality
- No screens 30-60 min before bed, or blue-light glasses
- Caffeine has 5-6 hour half-life — cut off by 2pm if sleeping at 10pm

### 2. Movement
- **Minimum viable**: 8,000-10,000 steps/day + 2x strength sessions/week
- Walking is underrated — 30 min/day reduces all-cause mortality significantly
- Strength training preserves muscle mass (critical after 35) and improves metabolism
- Cardio: 150 min moderate or 75 min vigorous per week (guidelines)
- Exercise snacks (10-min walks after meals) beat one long session if time-constrained

### 3. Nutrition Principles
- **Protein first**: 0.7-1g per pound of bodyweight to preserve muscle
- **Minimize ultra-processed foods** (not "clean eating" — just less UPF)
- **Hydration**: half your bodyweight in ounces daily minimum
- Eat slowly, recognize hunger/fullness cues
- No single food is magic; no single food is poison

### 4. Stress Management
- Physiological sigh (double inhale through nose, long exhale through mouth) — immediate calm
- 10 min daily mindfulness or body scan — builds long-term resilience
- Social connection is the most underrated health intervention

## Guidance Rules
- Always recommend consulting a doctor for specific medical conditions
- Give ranges, not rigid rules — sustainability beats perfection
- Prioritize behavioral change over supplements
- Acknowledge that sleep deprivation makes everything else harder
""",
        "requires_env": [],
    },
    {
        "slug": "event-planner",
        "name": "Event Planner",
        "description": "End-to-end event planning — birthday dinners, group trips, celebrations, corporate outings. Covers logistics, vendor selection, and contingencies.",
        "category": "Productivity",
        "tags": ["events", "planning", "organizing", "celebrations", "logistics"],
        "icon": "🎉",
        "readme_url": "https://clawhub.ai/skills/event-planner",
        "downloads": 2988,
        "content": """# Event Planner

You plan events that people remember. Structure, flexibility, and the right details in the right order.

## Planning Timeline

### 6+ weeks out
- Confirm date and guest count
- Lock the venue (availability drives all other decisions)
- Set budget and split responsibility if shared

### 3-6 weeks out
- Send save-the-dates / invitations
- Confirm catering / restaurant reservation
- Book entertainment, photographer, or special elements
- Create event budget tracker

### 1-2 weeks out
- Final headcount RSVP
- Confirm all vendors (call, don't assume)
- Plan day-of logistics: parking, arrival flow, seating
- Create a run-of-show timeline

### Day before
- Confirm all deliveries and arrivals
- Prepare any welcome materials or decorations
- Charge devices, print backup copies of key info

## Budget Framework by Event Type

| Event | Budget per Person |
|-------|------------------|
| Home dinner party | $20-50 |
| Restaurant group dinner | $60-120 |
| Birthday celebration | $50-150 |
| Wedding (mid-range) | $100-200 |
| Corporate outing | $75-200 |

## Vendor Selection Criteria
1. Reviews from similar event types (not just overall rating)
2. Responsiveness during inquiry (signals day-of reliability)
3. Clear contracts with cancellation policy
4. Have backup vendors researched (never single point of failure)

## Contingency Planning
Always prepare for:
- Weather (outdoor events need indoor backup)
- No-shows (order/cater for 85% of confirmed RSVPs)
- Tech failures (AV, payments)
- Late key vendors — know their ETA and have a plan B

## Communication Templates
For invitations: Venue + date + time + dress code + RSVP deadline + parking info
For vendors: Confirm arrival time, setup requirements, contact number, payment terms
""",
        "requires_env": [],
    },
    {
        "slug": "meal-planner",
        "name": "Meal Planner",
        "description": "Personalized weekly meal planning, grocery lists, and recipe suggestions based on preferences, budget, and nutrition goals.",
        "category": "Lifestyle",
        "tags": ["meals", "recipes", "cooking", "grocery", "nutrition"],
        "icon": "🍽️",
        "readme_url": "https://clawhub.ai/skills/meal-planner",
        "downloads": 4156,
        "content": """# Meal Planner

You create practical meal plans that people will actually follow — not aspirational plans that fall apart by Wednesday.

## Meal Planning Framework

### Step 1 — Gather Constraints
Before planning, confirm:
- Dietary restrictions and preferences (allergies, vegetarian, halal, etc.)
- Cooking skill level (beginner / comfortable / confident)
- Time available on weekdays vs. weekends
- Budget per week for groceries
- Kitchen equipment available (oven, instant pot, air fryer, etc.)
- How many people eating, including kids

### Step 2 — Structure the Week
**Realistic week structure:**
- 2-3 cook-from-scratch dinners (weekends + one weekday)
- 2 batch-cooked meals (one recipe, double portion, eat twice)
- 1-2 quick assembly meals (grain bowls, wraps, pasta from pantry)
- 1 "free" dinner (takeout, leftovers, whatever)

**Breakfast:**
- Default to 2-3 rotating options (not 7 different breakfasts)
- Overnight oats, eggs, or yogurt+fruit = low decision fatigue

**Lunch:**
- Batch cook a grain + protein Sunday → 4 days of lunches
- Or plan to use dinner leftovers

### Step 3 — Build the Grocery List
Organize by store section:
- Produce (shop freshest first mid-week)
- Protein (can be frozen if not using within 2 days)
- Pantry staples
- Dairy

Apply the 80% rule: buy staples you always use, buy perishables only for planned recipes.

### Step 4 — Recipe Selection Principles
- Each recipe should share ingredients with another (reduce waste)
- One "hero protein" per week (whole chicken, large cut) → multiple meals
- Seasonal produce = better flavor + lower cost

## Output Format
Present meal plans as:
- **Monday-Sunday dinner grid** (with links/descriptions for each meal)
- **Shopping list** organized by category
- **Prep tip** for the week (e.g., "Cook rice Sunday for 3 lunches")
- **Nutrition notes** if health goals were specified
""",
        "requires_env": [],
    },
    {
        "slug": "home-organizer",
        "name": "Home Organizer",
        "description": "Smart home organization and decluttering systems. Practical frameworks for organizing spaces, reducing clutter, and maintaining order.",
        "category": "Lifestyle",
        "tags": ["organization", "declutter", "home", "storage", "minimalism"],
        "icon": "🏠",
        "readme_url": "https://clawhub.ai/skills/home-organizer",
        "downloads": 2341,
        "content": """# Home Organizer

You help people create systems that keep homes organized — not just one-time clean-outs.

## The Organization Hierarchy

### 1. Declutter First (always before organizing)
The rule: only organize things worth keeping.

**Decision framework for each item:**
- Have I used this in the last 12 months?
- Would I buy this again today?
- Does it serve a function I actually need?
- Does keeping it cost more (space, maintenance) than it provides?

**Categories for everything:**
- Keep → goes to its designated place
- Donate → box, ready to leave within 48 hours
- Sell → only if realistic; set a 2-week deadline or donate
- Trash → immediate

### 2. Assign Homes for Everything
"A place for everything, everything in its place."
- Items used together live together
- Items used frequently live nearest to point of use
- Like categories together (all batteries in one drawer, not three)

### 3. Contain Before Labeling
Containers create visual order even in drawers/shelves:
- Measure before buying containers
- Use uniform containers in the same space (visual calm)
- Label once the system is stable (not before)

## Room-by-Room Priorities

**Kitchen**: Purge duplicates → zone by task (prep zone, cooking zone, cleanup zone) → decant pantry staples for visibility

**Bedroom**: Empty nightstand to essentials only → capsule wardrobe principles → under-bed storage for seasonal items

**Entryway**: Every person gets one hook + one shelf. Anything without a home breeds chaos.

**Garage/Storage**: Vertical storage (wall-mounted) > floor storage. Label everything.

## Maintenance Systems
- **One in, one out rule**: New item comes in → old item goes out
- **10-minute reset**: Same time daily, everything goes back to its home
- **Seasonal audit** (2x/year): Rotate seasonal items, reassess what's no longer needed
""",
        "requires_env": [],
    },
]


def seed_skills_catalog(db_path=None) -> None:
    """Insert starter skills into the catalog (skip existing slugs)."""
    conn = get_db(db_path)
    try:
        for skill in _STARTER_SKILLS:
            existing = conn.execute(
                "SELECT slug FROM skills_catalog WHERE slug = ?", (skill["slug"],)
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """INSERT INTO skills_catalog
                   (slug, name, description, category, tags_json, icon, readme_url, content,
                    requires_env_json, downloads, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'clawhub')""",
                (
                    skill["slug"],
                    skill["name"],
                    skill["description"],
                    skill["category"],
                    json.dumps(skill["tags"]),
                    skill["icon"],
                    skill["readme_url"],
                    skill["content"],
                    json.dumps(skill.get("requires_env", [])),
                    skill.get("downloads", 0),
                ),
            )
        conn.commit()
        logger.info("Skills catalog seeded (%d starter skills)", len(_STARTER_SKILLS))
    finally:
        conn.close()


# ─── Catalog queries ──────────────────────────────────────────────────────────

def list_catalog(db_path=None, category: str | None = None, q: str | None = None) -> list[dict]:
    conn = get_db(db_path)
    try:
        sql = "SELECT * FROM skills_catalog"
        params: list = []
        filters = []
        if category:
            filters.append("category = ?")
            params.append(category)
        if q:
            filters.append("(name LIKE ? OR description LIKE ? OR tags_json LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like, like])
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY downloads DESC"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_skill(slug: str, db_path=None) -> dict | None:
    conn = get_db(db_path)
    try:
        row = conn.execute("SELECT * FROM skills_catalog WHERE slug = ?", (slug,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.pop("tags_json", "[]"))
    d["requires_env"] = json.loads(d.pop("requires_env_json", "[]"))
    return d


# ─── User skill management ────────────────────────────────────────────────────

def get_user_skills(user_handle: str, db_path=None) -> list[dict]:
    """Return all installed skills for a user (with catalog metadata)."""
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT us.*, sc.name, sc.description, sc.category, sc.icon, sc.tags_json,
                      sc.readme_url, sc.requires_env_json, sc.downloads
               FROM user_skills us
               JOIN skills_catalog sc ON sc.slug = us.skill_slug
               WHERE us.user_handle = ?
               ORDER BY us.installed_at DESC""",
            (user_handle,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.pop("tags_json", "[]"))
            d["requires_env"] = json.loads(d.pop("requires_env_json", "[]"))
            d["config"] = json.loads(d.pop("config_json", "{}"))
            result.append(d)
        return result
    finally:
        conn.close()


def install_skill(user_handle: str, slug: str, db_path=None) -> dict:
    """Install a skill for the user. Fetches content from GitHub if not cached."""
    conn = get_db(db_path)
    try:
        skill = conn.execute(
            "SELECT slug, content FROM skills_catalog WHERE slug = ?", (slug,)
        ).fetchone()
        if not skill:
            raise ValueError(f"Skill '{slug}' not found in catalog")

        # If content is empty, try to fetch from GitHub
        if not skill["content"] and skill["slug"]:
            conn.close()
            _fetch_and_cache_content(slug, db_path)
            conn = get_db(db_path)

        conn.execute(
            """INSERT INTO user_skills (user_handle, skill_slug, enabled)
               VALUES (?, ?, 1)
               ON CONFLICT(user_handle, skill_slug) DO UPDATE SET enabled = 1""",
            (user_handle, slug),
        )
        conn.commit()
        return {"ok": True, "slug": slug}
    finally:
        conn.close()


def uninstall_skill(user_handle: str, slug: str, db_path=None) -> dict:
    conn = get_db(db_path)
    try:
        conn.execute(
            "DELETE FROM user_skills WHERE user_handle = ? AND skill_slug = ?",
            (user_handle, slug),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def toggle_skill(user_handle: str, slug: str, enabled: bool, db_path=None) -> dict:
    conn = get_db(db_path)
    try:
        conn.execute(
            "UPDATE user_skills SET enabled = ? WHERE user_handle = ? AND skill_slug = ?",
            (1 if enabled else 0, user_handle, slug),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def save_skill_config(user_handle: str, slug: str, config: dict, db_path=None) -> dict:
    conn = get_db(db_path)
    try:
        conn.execute(
            "UPDATE user_skills SET config_json = ? WHERE user_handle = ? AND skill_slug = ?",
            (json.dumps(config), user_handle, slug),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def get_skill_instructions(user_handle: str, db_path=None) -> str:
    """Return concatenated SKILL.md content for all enabled skills (for agent injection)."""
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT sc.name, sc.content
               FROM user_skills us
               JOIN skills_catalog sc ON sc.slug = us.skill_slug
               WHERE us.user_handle = ? AND us.enabled = 1 AND sc.content != ''
               ORDER BY us.installed_at""",
            (user_handle,),
        ).fetchall()
        if not rows:
            return ""
        parts = []
        for r in rows:
            parts.append(f"\n\n═══ SKILL: {r['name']} ═══\n{r['content']}")
        return "\n".join(parts)
    finally:
        conn.close()


def create_skill_tools(user_handle: str, db_path=None) -> list:
    """Create ADK-compatible tool functions for each enabled user skill.

    Each skill becomes a no-argument callable that returns the SKILL.md content.
    When the agent calls the tool, the tool event appears in the chat UI.
    """
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT sc.slug, sc.name, sc.content, sc.icon
               FROM user_skills us
               JOIN skills_catalog sc ON sc.slug = us.skill_slug
               WHERE us.user_handle = ? AND us.enabled = 1 AND sc.content != ''
               ORDER BY us.installed_at""",
            (user_handle,),
        ).fetchall()
    finally:
        conn.close()

    tools = []
    for row in rows:
        slug = row["slug"]
        name = row["name"]
        content = row["content"]
        fn_name = "apply_" + slug.replace("-", "_").replace("/", "_") + "_skill"

        def _make_skill_tool(skill_content: str, skill_name: str, func_name: str):
            def skill_tool() -> dict:
                return {"result": skill_content}

            skill_tool.__name__ = func_name
            skill_tool.__qualname__ = func_name
            skill_tool.__doc__ = (
                f"Retrieve the '{skill_name}' skill guidelines. "
                f"Call this when the user's request relates to {skill_name} topics "
                f"to get detailed instructions for applying this skill."
            )
            return skill_tool

        tools.append(_make_skill_tool(content, name, fn_name))

    return tools


# ─── ClawhHub browsing (GitHub API) ──────────────────────────────────────────

async def browse_clawhub(query: str = "", limit: int = 20) -> list[dict]:
    """Search the openclaw/skills GitHub repo for skills matching the query."""
    q = f"filename:SKILL.md repo:openclaw/skills {query}".strip()
    url = "https://api.github.com/search/code"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"q": q, "per_page": limit}, headers=headers)
        if resp.status_code != 200:
            return []
        data = resp.json()
    results = []
    for item in data.get("items", []):
        path = item.get("path", "")
        parts = path.split("/")
        # path format: skills/{username}/{skill-name}/SKILL.md
        if len(parts) == 4:
            skill_name = parts[2].replace("-", " ").title()
            slug = f"{parts[1]}/{parts[2]}"
            results.append({
                "slug": slug,
                "name": skill_name,
                "description": f"Skill from clawhub: {parts[1]}/{parts[2]}",
                "category": "ClawhHub",
                "icon": "🔧",
                "readme_url": item.get("html_url", ""),
                "raw_url": f"https://raw.githubusercontent.com/openclaw/skills/main/{path}",
                "in_catalog": False,
            })
    return results


async def import_from_clawhub(slug: str, raw_url: str, db_path=None) -> dict:
    """Fetch a skill from GitHub and add it to the local catalog."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(raw_url)
        resp.raise_for_status()
        content = resp.text

    # Parse frontmatter if present
    name = slug.split("/")[-1].replace("-", " ").title()
    description = ""
    if content.startswith("---"):
        lines = content.split("\n")
        for line in lines[1:]:
            if line.startswith("---"):
                break
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"\'')
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"\'')

    conn = get_db(db_path)
    try:
        conn.execute(
            """INSERT INTO skills_catalog
               (slug, name, description, category, tags_json, icon, readme_url, content,
                requires_env_json, downloads, source)
               VALUES (?, ?, ?, 'ClawhHub', '[]', '🔧', ?, ?, '[]', 0, 'clawhub')
               ON CONFLICT(slug) DO UPDATE SET content = excluded.content""",
            (slug, name, description, f"https://clawhub.ai/skills/{slug}", content),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "slug": slug, "name": name}


def _fetch_and_cache_content(slug: str, db_path=None) -> None:
    """Synchronously fetch SKILL.md for a seeded skill that had no content."""
    # Seeded skills already have content inline — this is a no-op for them.
    pass

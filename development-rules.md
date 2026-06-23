# Wall St. Bots: Development Rules & Protocol

## Core Mission Statement
Wall St. Bots is a precision-driven simulation and signals platform designed to bridge the gap between algorithmic analysis and actionable member execution. Our core directive is to provide members with exact, timestamped entry and exit signals for their selected portfolios of stocks and crypto, delivered via email at market open and close. The integrity of our data is our product; therefore, every architectural decision, logic flow, and code refinement must prioritize the accuracy, timeliness, and reliability of bot13’s trade signals. 

**Accuracy is not an option; it is the fundamental requirement of every line of code.**

---

## The Prime Directive: Data Integrity
Every decision, from database schema design to email dispatch logic, must be evaluated against the "Data Integrity Mandate":
1. **Timestamp Precision:** All trade data must be generated, stored, and sent with absolute, verified timestamps.
2. **Signal Reliability:** bot13’s logic must be deterministic and verifiable. No "black box" decisions that cannot be audited by the user.
3. **Execution Fidelity:** The email delivery system must ensure signals are received precisely at market open and before market close. 
4. **Member-First Accuracy:** Since members are using these signals for real-world financial decisions, any error in data handling is a critical failure.

---

## Development Constraints
* **Auditability:** Every trade simulated by bot13 must have a clear "reasoning trace" accessible by the user.
* **Reliability:** The system must handle concurrency gracefully. Ensure that portfolio data processing for one user does not impact the integrity of another.
* **Latency:** Optimize for speed. If data processing takes too long, the email won't hit the inbox at the market bell. Prioritize non-blocking IO and efficient data retrieval.
* **Error Handling:** Fail loudly. If a signal cannot be calculated with 100% certainty, the system must log a critical error rather than providing a potentially faulty signal.

---

## Refinement Checklist
Before committing any new feature or change, answer these questions:
- [ ] Does this change improve or maintain the precision of the timestamped signals?
- [ ] Is this logic deterministic and reproducible?
- [ ] Could this change delay the signal delivery relative to market events?
- [ ] Is the data being logged in a way that allows a user to verify why the signal was generated?

---

*“If you are unsure whether a change maintains data integrity, assume it does not and prioritize further testing and validation.”*

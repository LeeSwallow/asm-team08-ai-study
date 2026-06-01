SUMMARY_SYSTEM_PROMPT = """
Summarize only supplied dialogue logs and discovered evidence for a player note.
You may include Backend supplied public storyline context: currentObjective, currentActId, publicPremise, openingObjective, visibleTimeline.
Keep source IDs when possible and do not infer missing case facts.
Never use forbidden private refs: secret, solution, privateTimeline, privateEvents, privateMotive, privateRefs, culprit, culpritId, isCulprit, finalDiscovery, finalVerdict, actualAction, actualLocation, or secretNote.
"""

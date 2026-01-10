# HVAC Comfort Start — Architecture

**Version:** Beta 9  
**Status:** Stable Beta  
**Platform:** Home Assistant + Pyscript

This document describes the internal architecture of the HVAC Comfort Start system and the design principles behind its adaptive preheat control logic.

---

## Design Goals

HVAC Comfort Start was designed to solve a specific and common problem:

> Reach the desired comfort temperature **at** the configured comfort time — not early, not late — across varying outdoor conditions and HVAC behavior.

Key goals:

- Eliminate fixed offsets and guesswork
- Learn from real heating cycles
- Remain stable across days (no oscillation)
- Survive restarts and configuration changes
- Prefer slight earliness over lateness

---

## High-Level Architecture

The system is divided into three independent but coordinated layers:



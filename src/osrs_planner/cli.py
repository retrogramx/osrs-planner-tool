import argparse
from osrs_planner.hiscores import fetch_stats
from osrs_planner.models import AccountMode
from osrs_planner.planner import generate_plan, load_goal



def main():
    parser = argparse.ArgumentParser(description="OSRS Planner Tool")
    parser.add_argument("command", help="Command to run (stats or plan)")
    parser.add_argument("rsn", help="Player name to look up")
    parser.add_argument("--mode", default="normal", help="Account mode")
    parser.add_argument("--skiller", action="store_true", help="Account is a level 3 skiller")
    parser.add_argument("--pure", action="store_true", help="Account is a 1 Defence pure")
    parser.add_argument("--goal", default="full_graceful", help="Goal ID (ex. full_graceful)")
    args = parser.parse_args()
    
    if args.command == "stats":
        account = fetch_stats(args.rsn, AccountMode[args.mode])
        print("=====================================")
        print(f"Username: {account.rsn} ({account.mode.value})")
        print("=====================================")
        for skill in account.skills.values():
            print(f"{skill.name:<15} Level {skill.level:<5} {skill.xp:>10,} XP")
    
    elif args.command == "plan":
        account = fetch_stats(args.rsn, AccountMode[args.mode])
        account.is_skiller = args.skiller
        account.is_pure = args.pure
        goal = load_goal(args.goal)
        plan_steps, warnings = generate_plan(account, goal)
        print("Retro: Greetings, traveller.")
        print("Retro: A plan, you ask?")
        print("Retro: ...well, here you go!")
        print("")
        print(f"Plan: {goal.name} for {account.rsn}")
        print(f"Current Agility: Level {account.skills['agility'].level} ({account.skills['agility'].xp:,} XP)")
        print(f"Target: {goal.target_marks} Marks of Grace")
        print("=====================================")
        print("")
        for warning in warnings:
            print(warning)
        print("")
        for i, step in enumerate(plan_steps, 1):
            print(f"Step {i}. {step['name']} ({step['from_level']} → {step['to_level']})")
            print(f"  XP needed: {step['xp_needed']:,.0f}")
            print(f"  Time left: ~{step['hours_left']:.1f} hrs")
            print(f"  Marks: ~{step['marks_earned']:.0f}")
            print("=====================================")
            
        total_hours = sum(step["hours_left"] for step in plan_steps)
        total_marks = sum(step["marks_earned"] for step in plan_steps)
        print(f" Total time: ~{total_hours:.1f} hrs left")
        print(f" Total marks: ~{total_marks:.0f}/260")
        print("")
        print("Retro: Good luck, adventurer!")

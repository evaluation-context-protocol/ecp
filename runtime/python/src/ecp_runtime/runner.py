"""
Docstring for runtime.python.src.ecp_runtime.runner

Simplified Version. V0.1
AsyncIO Pending
"""

import subprocess
import json
import os
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from .graders import evaluate_step
from rich import print

@dataclass
class StepResult:
    status: str
    public_output: Optional[str] = None
    private_thought: Optional[str] = None
    logs: Optional[str] = None

class AgentProcess:
    """Manages the lifecycle of the Agent Child Process."""
    
    def __init__(self, command: str):
        self.command = command
        self.process = None

    def start(self):
        # Launch the agent and connect pipes to stdio
        self.process = subprocess.Popen(
            self.command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # Line buffered
        )

    def stop(self):
        if self.process:
            self.process.terminate()

    def send_rpc(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sends a JSON-RPC request and waits for the response."""
        if not params:
            params = {}
            
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        # Write to Agent's STDIN
        json_str = json.dumps(request)
        self.process.stdin.write(json_str + "\n")
        self.process.stdin.flush()

        # Read from Agent's STDOUT
        # NOTE: A robust implementation needs a better read loop (asyncio)
        # This assumes the agent returns 1 line of JSON.
        response_line = self.process.stdout.readline()
        
        if not response_line:
            stderr = self.process.stderr.read()
            raise RuntimeError(f"Agent crashed or closed connection. Stderr: {stderr}")

        try:
            return json.loads(response_line)
        except json.JSONDecodeError:
            raise RuntimeError(f"Agent returned invalid JSON: {response_line}")

class ECPRunner:
    """The Orchestrator."""
    
    def __init__(self, manifest):
        self.manifest = manifest

    def run_scenarios(self):
        total_passed = 0
        total_checks = 0
        
        for scenario in self.manifest.scenarios:
            print(f"\n[bold blue]Scenario: {scenario.name}[/bold blue]")
            
            agent = AgentProcess(self.manifest.target)
            agent.start()
            
            try:
                agent.send_rpc("agent/initialize", {"config": {}})
                
                for i, step in enumerate(scenario.steps):
                    # Execute
                    rpc_resp = agent.send_rpc("agent/step", {"input": step.input})
                    result_data = rpc_resp.get("result", {})
                    
                    # Map to internal object
                    step_result = StepResult(
                        status=result_data.get("status", "done"),
                        public_output=result_data.get("public_output"),
                        private_thought=result_data.get("private_thought")
                    )
                    
                    print(f"  Step {i+1}: Input='{step.input}'")
                    print(f"  > Output: {step_result.public_output}")
                    if step_result.private_thought:
                         print(f"  > [dim]Thought: {step_result.private_thought}[/dim]")

                    # --- GRADING HAPPENS HERE ---
                    checks = evaluate_step(step, step_result)
                    
                    for check in checks:
                        total_checks += 1
                        icon = "✅" if check['passed'] else "❌"
                        color = "green" if check['passed'] else "red"
                        
                        # Print the verdict
                        print(f"    {icon} [{color}]{check['type']} on {check['field']}[/{color}]")
                        
                        # Print the reasoning if it's interesting (LLM Judge or Failure)
                        if check['type'] == "llm_judge" or not check['passed']:
                            print(f"       [dim]Reason: {check['reasoning']}[/dim]")

                        if check['passed']:
                            total_passed += 1
            
            finally:
                agent.stop()
        
        print(f"\n[bold]Run Complete. Passed: {total_passed}/{total_checks}[/bold]")
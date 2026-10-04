"""Crew 2: the writer drafts from the evidence, then the verifier prunes it (config/*.yaml)."""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from agents.crews import VerifiedAnswer, build_llm
from core.models import AISettings


@CrewBase
class AnswerCrew:
    """Writer then verifier, sequential; final output ``VerifiedAnswer``."""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def writer(self) -> Agent:
        return Agent(config=self.agents_config['writer'], llm=build_llm(), verbose=False)

    @agent
    def verifier(self) -> Agent:
        return Agent(config=self.agents_config['verifier'], llm=build_llm(VerifiedAnswer, model=AISettings.load().verifier_model or None),
                     verbose=False)

    @task
    def write(self) -> Task:
        return Task(config=self.tasks_config['write'])

    @task
    def verify(self) -> Task:
        return Task(config=self.tasks_config['verify'], output_pydantic=VerifiedAnswer)

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=False)

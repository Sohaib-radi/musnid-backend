"""Crew 1: language, level and Arabic search query of a question (config/*.yaml)."""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from agents.crews import Classification, build_llm


@CrewBase
class ClassifyCrew:
    """One agent, one task, structured output ``Classification``."""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def classifier(self) -> Agent:
        return Agent(config=self.agents_config['classifier'], llm=build_llm(Classification), verbose=False)

    @task
    def classify(self) -> Task:
        return Task(config=self.tasks_config['classify'], output_pydantic=Classification)

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=False)

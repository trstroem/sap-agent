import asyncio
#from typing import Any

from semantic_kernel.functions import kernel_function

from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from azure.ai.projects import AIProjectClient

from semantic_kernel.functions import KernelArguments

from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file


async def initialize_agent_settings() -> AzureAIAgentSettings:
    """
    Initialize and return the Azure AI agent settings.
    
    Returns:
        AzureAIAgentSettings: Configured settings for the Azure AI agent.
    """
    return AzureAIAgentSettings.create() # Note the variable configuration prerequisites in your .env


async def create_agent_client(credential: DefaultAzureCredential):
    """
    Create and return an Azure AI agent client.
    
    Args:
        credential (DefaultAzureCredential): Azure credential for authentication.
        
    Returns:
        AzureAIAgentClient: Client for interacting with Azure AI agent service.
    """
    return AzureAIAgent.create_client(credential=credential)

    


class Products_Plugin:
    description = "A plugin to retrieve information about products. It returns a JSON object with various information about the product."
    
    # Define a function to call the Logic App
    @kernel_function
    async def retrieve_product_information(self,
                                           product_id: str = KernelArguments(description="The ID of the product to retrieve information for.")):

        """Calls an Azure Logic App to get product information."""
        logic_app_url = os.getenv("PRODUCTS_APP_URL")

        payload = {
            "Product_ID": product_id
        }
        headers = {
            "Content-Type": "application/json"
        }

        import requests

        response = requests.post(logic_app_url, json=payload, headers=headers)
    
        # Here, I am providing sample code (commented out) for printing the JSON response
        # from the Logic App. This can be crucial for testing and debugging purposes...
        #if response.status_code == 200:
            #print("Logic App called successfully!")
            #print("Response:", response.json())
        #else:
            #print(f"Failed to call Logic App. Status code: {response.status_code}")
            #print("Error:", response.text)

        return response.json()



async def setup_agent(
    client:  AIProjectClient, 
    settings: AzureAIAgentSettings,
    name: str = "Assistant",
    instructions: str = "Answer the user's questions."
):
    """
    Set up an Azure AI agent and create a conversation thread.
    
    Args:
        client (AIProjectClient): Client for interacting with Azure AI agent service.
        settings (AzureAIAgentSettings): Configured settings for the Azure AI agent.
        name (str, optional): Name of the agent. Defaults to "Assistant".
        instructions (str, optional): Instructions for the agent. Defaults to "Answer the user's questions."
        
    Returns:
        Tuple[AzureAIAgent, Thread]: The created agent and conversation thread.
    """
    # Create an agent definition on the Azure AI agent service
    agent_definition = await client.agents.create_agent(
        model=settings.model_deployment_name,  # Configured in your .env file
        name=name,
        instructions=instructions,
    )
    
    # Create a Semantic Kernel agent for the Azure AI agent
    agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        plugins=[Products_Plugin()],  # Add the Products plugin to the agent
    )

    # Create a thread for the agent
    thread: AzureAIAgentThread = AzureAIAgentThread(client=client)

    return agent, thread


async def process_user_input(
    user_input: str, 
    client: AIProjectClient,
    agent: AzureAIAgent, 
    thread: AzureAIAgentThread
):
    """
    Process user input and handle special commands.
    
    Args:
        user_input (str): The input provided by the user.
        agent (AzureAIAgent): The Azure AI agent.
        thread (Thread): The current conversation thread.
        client (AzureAIAgentClient): Client for interacting with Azure AI agent service.
        
    Returns:
        Optional[Thread]: A new thread if the conversation was cleared, None otherwise.
    """
    # Handle quit command
    if user_input.lower() in ["quit", "q"]:
        print("Goodbye!")
        return None
    
    # Handle clear command - reset the conversation by creating a new thread
    if user_input.lower() in ["clear"]:
        new_thread: AzureAIAgentThread = AzureAIAgentThread(client=client)
        #new_thread: AzureAIAgentThread = AzureAIAgentThread()
        #new_thread = await agent.create_thread()
        print("Conversation history cleared. Starting fresh.")
        return new_thread

    # Handle empty input
    if not user_input.strip():
        print("Please enter valid, non-empty input.")
        return thread
    
    #await agent.add_chat_message(thread_id=thread.id, message=user_input)
    #print("Generating response...")
    
    response = await agent.get_response(thread=thread, messages=user_input)
    print(f"# {response.name}: {response}")
    print("\n" + "-" * 50 + "\n")
    return thread


async def cleanup_resources(
    client:  AIProjectClient, 
    thread: AzureAIAgentThread, 
    agent_id: str
) -> None:
    """
    Clean up resources by deleting the thread and agent.
    
    Args:
        client (AzureAIAgentClient): Client for interacting with Azure AI agent service.
        thread_id (str): ID of the thread to delete.
        agent_id (str): ID of the agent to delete.
    """
    await thread.delete() if thread else None
    await client.agents.delete_agent(agent_id)


async def run_chat_loop(
    agent: AzureAIAgent, 
    thread: AzureAIAgentThread, 
    client:  AIProjectClient
) -> None:
    """
    Run the main chat loop for interacting with the agent.
    
    Args:
        agent (AzureAIAgent): The Azure AI agent.
        thread (Thread): The conversation thread.
        client (AzureAIAgentClient): Client for interacting with Azure AI agent service.
    """
    current_thread = thread
    
    try:
        print("\n===== Azure AI Agent Chat with SK =====")
        print("Starting a new conversation. Type 'quit' to exit or 'clear' to reset the conversation.\n")
        
        # Chat loop - continue until user quits
        while True:
            user_input = input("Enter a question (or 'quit' to exit, 'clear' to reset): ")
            
            result_thread = await process_user_input(user_input, client, agent, thread)
            
            if result_thread is None:
                break

            current_thread = result_thread
            
    finally:
        await cleanup_resources(client, current_thread, agent.id)


async def main() -> None:
    """
    Main function that orchestrates the Azure AI agent chat with SK example.
    
    This function initializes the agent settings, creates the agent client,wha 
    sets up the agent and thread, and runs the chat loop.
    """
    print("Initializing Azure AI Agent settings...")
    ai_agent_settings = await initialize_agent_settings()

    async with DefaultAzureCredential() as creds, \
               await create_agent_client(creds) as client:

        agent, thread = await setup_agent(client, ai_agent_settings)
        
        # Run the chat loop
        await run_chat_loop(agent, thread, client)


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
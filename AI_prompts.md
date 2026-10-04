# HW5 AI Prompts

Every prompt I gave the AI assistant (Claude Code) during Homework 5, word for word, grouped by problem.

## Problem 1

### Setup

1. In light of recent events, let's pivot to AI hw 5. Please put everything we're about to do in the hw5 folder in AL Class

### Problem 1

1. Make an AI_promots folder that records everything I tell you. There should be spaces there for problems 1-11. This is problem 1

## Problem 2

1. Thank you. For Q2, make output/harness.md. In it, put this, verbatim: The database has nine tables that AI agents can use to understand and work with Campus Customs. The cash accounts table includes name, balance, and date, and it matters because it tells agents how much money is available in each account and when that balance was recorded. The desk table includes today’s date and notes, and it gives agents the current date and any general notes they should know before making decisions. The inventory table includes SKU, product name, size, quantity, and location, and it matters because it tells agents what products are available, how many are in stock, their sizes, and where they are located. The invoices table includes invoice ID, vendor ID, amount, due date, status, and description, and it lets agents see what the company owes vendors, when payments are due, and whether they have already been paid. The leases table includes lease ID, space name, landlord, monthly rent, next due date, and notes, and it gives agents information about the company’s rented spaces, including how much rent costs and when it is due. The payments table includes payment ID, type, reference ID, amount, account, payment date, and approved by, and it gives agents a record of payments that have been made, including what was paid, which account was used, when it was paid, and who approved it. The pricing table includes SKU, unit cost, and list price, and it matters because it tells agents how much each product costs the company and how much the company sells it for. The tickets table includes ticket ID, type, requester, subject, SKU, size, quantity, lease ID, invoice ID, status, notes, and creation date, and it gives agents the requests or tasks they may need to handle while connecting those requests to products, leases, or invoices when necessary. Finally, the vendors table includes vendor ID, name, specialty, and lead time in days, and it tells agents who the company buys from, what each vendor specializes in, and how long they usually take to deliver.

## Problem 3

1. For Q3, let's make an MCP server in mcp_server/ using FastMCP. It will eventually talk to data/campusgroups_new.db. Every agent in this homework will use this MCP server. We'll add 3 tools to it once it's made
2. 1. get_ticket - this will retrive all info for 1 ticket. 2. search_ticket - this will find tickets based on searched criteria. 3. update_ticket - this will allow us to update tickets. Also, never invent data, only use what is in the database
3. Scratch those. Let's make 3 new tools. You can delete the others
4. Create these three MCP tools:

   * `check_inventory` — Takes a SKU and size and returns how many units of that specific product and size are currently in stock.
   * `get_product_pricing` — Takes a SKU and returns the product’s unit cost and list price.
   * `get_lease_details` — Takes a lease ID and returns the relevant lease information, including the landlord, rent amount, and due date.

5. Put this in output/harness.md: The **check_inventory** tool reads the **inventory table** and helps unlock **tickets 101 and 103**. It checks how many units of a specific product and size are currently in stock so the agent can determine whether there is enough inventory to fulfill the request. The **get_product_pricing** tool reads the **pricing table** and helps unlock **ticket 103**. It returns the unit cost and list price for a specific product so the agent has the pricing information needed to evaluate the requested bulk discount. The **get_lease_details** tool reads the **leases table** and helps unlock **ticket 102**. It returns the relevant information about a specific lease, including the landlord, rent amount, and due date, so the agent can understand and respond to the rent notice.
6. Make mcp_server/README.md and put this in it: I am planning to create three tools for the MCP server. The first is **check_inventory**, which will read the inventory table and check how many of a certain product and size are in stock. This will help with tickets 101 and 103, and it will return the SKU, size, and quantity available. The second is **get_product_pricing**, which will read the pricing table and find the cost and list price of a product. This will help with ticket 103, and it will return the SKU, unit cost, and list price. The third is **get_lease_details**, which will read the leases table and find the important information about a lease. This will help with ticket 102, and it will return the lease ID, landlord, rent amount, and due date.

## Problem 4

1. Ty. Time for Q4
2. Add the MCP server to this project (hw5) so you can call all of my tools. Save the connection JSON text in .mcp.json at the project root
3. Make output/mcp_smoke.json. Put all three of this, as well as its output (it should match data/campus_customs_new.db) in it. check_inventory: “Do we have enough small Bulldog tees in stock to fulfill ticket 101?”
   get_product_pricing: “What is the cost and list price of the hoodie in ticket 103?”
   get_lease_details: “How much rent do we owe for the lease in ticket 102, who do we owe it to, and when is it due?”

## Problem 5

1. Time for Q5
2. Using PydanticAI, let's make a team of agents that work together. They can delegate each other tasks and can connect with each other with full connectivity. Their goal is to respond to tickets. They are as follows: Boss - reads the ticket and delegates it. Makes final call when necessary. Inventory - checks stock by SKU and size, spots when low, decides the vendor to restock. Accounting - Looks over cash and invoices, checks margins, and prepares purchase orders for human approval. Facilities - In charge of shop upkeep (rent, lease, etc). Customer Service - drafts messages for customers for human review. Put the prompts for all the agents in backedn/prompts/ and data types in backend/models.py, and the agent files under backend/. You can use my portkey apo key if necessary. Give the tools all the abilities they need to do their said jobs
3. Add any tools that the agents need so they can work on the open tickets. All shop facts should come from the MCP server over data/campus_customs_new.db. Do not invent any second shop-tools that bypass the MCP. All agents should append to output/audit_trail.json as they run. Record each loop step, and do not clear after loops.
4. What other tools did you give the agent?
5. Please list all of them in output/harness.md. Also include the following safety guidelines: Agents should never make a payment, refund, or any customer communication without human approval. Each agent should loop a maximum of 7 times before it fails.
6. Did you run the agents already?
7. Don't if you haven't yet

## Problem 6

1. Okay. Let's move on to Q6. We're gonna pretend they haven't been run yet
2. Before we do that, please add in the safety deck that agents should not run unless explicitly asked. The boss must be asked by a human, and the others by either the boss or a human
3. No, that can stay
4. Thanks CC. Please build output/desk_tickets.html. This should be a page I can doubleclick that has one tab per ticket. Also add a blank 'cash' and 'reflections' tab. There should also be an 'expected' section, and I'll tell you what to put in there. And a blank 'actual' section that will describe exactly what happens when we run the agents. In the expected section, write this for ticket 1: The boss will call inventory, who will check the amount of S bulldog tee's we have. Inventory then tell us which supplier will restock it if necessary. Do this for ticket 2: The boss should call facilities, who will tee up a rent payment for a human to easily do. For ticket 3, the boss will call inventory to see if the ask is feasible, and may check with accounting to see what a reasonable charge is. It will then call customer service, who will draft a response email for human review
5. Thanks CC, you killed it. I'm gonna take a break, but next will be Q7
6. What's in there rn?
7. Oh. You can delete those
8. (asked later, during the Q11 edits) For question 6, can you add something about the MCP servers that are expected for each run?

## Problem 7

1. We're back because it's raining. In Q8, we're gonna build a dashboard. But here in Q7, we're gonna make a backend. Make a backend using FastAPI and use routes that do the following: return the 3 tickets and give their resolve status, take a ticket id and run the agent team on said ticket, return agent events, approve a payment or purchase after a human clicks approve, return current checking balance from cash_accounts, and reset the data base to original values when we want a fresh run. Lastly, from the backend folder, start the server with uvicorn main:app --reload --port 8000
2. Let's move on to Q8 after the break

## Problem 8

1. Time for Q8. Build a frontend dashboard in frontend/ with React, Vite, and Typescript. It should call the routes I made in Q7. It should: list all 3 tickets, start the agent on the first ticket, show all the agents and what they are doing when solving each ticket, show a ticket as resolved when finished, provide a short summary of what each agent did on the ticket, let a human pay or approve purchases when asked, and show the checking balance.  The front end should talk to the backend at http://localhost:8000. Allow the Vite page origin on the backend so the browser can call those routes. Start the board with: npm run dev. Make it look fun and creative
2. Me gusta. Can we give it Yale colors and style it similar to how we build the website in hw4? So with some bulldogs fighting other ivy mascots, and a Yale sports ticker? I like the emojis a lot
3. Thank you. Write this in output/design.md: I made the dashboard Yale themed, and added fun graphics of us beating other ivy league schools and a Yale sports ticker so users can keep track of how the Bulldogs are doing. I made the layout easy to navigate with the tickets on the side, and added fun emojis that light up for each agent. When the agent is thinking, the emojis dance/light up. The agent activity is tracked like a twitter feed, so it looks fun and is enjoyable for users to follow. Also the checking feed looks like a piggy bank

## Problem 9

1. Time for Q9. Can you reset the database? Then note the starting balance. We then need to run all 3 tickets until each is resolved. Note the EXACT steps each agent tool (and the agents we used) on the actual section from Q6. Keep the expected tab Q6 the same.  Then, on the cash tab, itemize the money. Note the starting check balance (after we reset it), how cash changed after each ticket and why, and the ending balance. It should match cash_accounts in the database. The math must be correct or I'll lose points and be sad. Also save output/resolved_tickets.json for ticket id, final status, short outcome, what each agent contributed, and all human approvals. Additionally, make output/resolved_board.html. This will be a link I can doubleclick that has a screenshot of my React board for each resolved ticket. Append these real runs to output/audit_trail.json. Lastly, make sure output/harness.nd covers tables, MCP tools, the 5 agents, API routes, the dashboard, and safety rules. ty
2. Just to confirm, nothing will actually happen if I approve the purchase, correct?
3. (Answer to Claude's question about ticket 103's $264.00 PO) Approve the PO
4. I'm impressed, thanks CC
5. Can you open the thing with the cash tab?

## Problem 10

1. Boola boola! For Q10, let's open the reflections tab and fill it out. "I would rate the boss's performance good overall, he understood the issues and who to delegate them to. I was also impressed by its recommended discount on the bulk order. I thought Facilities nailed the second ticket, and Inventory correctly identified the gaps between stock and order, and identified the correct supplier to remedy them. I liked how accounting checked the recommendations, and it seemed to do a good job of keeping the numbers in place. My issue is with customer service. It needs to wait until after I approve the other agent's work to do its work, as it's too transparent about issues. For example, we shouldn't be telling customers that we don't have items in stock; we should tell them when we expect to be able to fulfill their order. With the exception of the second ticket, which went straight from the boss to facilities, the other tickets had more steps than I expected. In particular, accounting had a larger role than I anticipated, as they handled everything with numbers. It may have been simpler to delegate some of the number tools to other agents, such as inventory. Three problems that Campus Customs could solve with these tools are: preparing purchases of new clothing items, paying the water bill, and handling the return of an item. What they could not do are: manage employee salary/hours (I would need an agent that handles employee information to take care of that), answer questions about store hours/location (there is nothing that deals with the physical location of the store), and estimate time for deliveries (there is no agent that deals with shipping time and how it varies by location).
2. (asked later, during the Q11 edits) Thanks CC. I also need to redo Q10. Make it say this instead: "101: I would give the performance on this ticket a solid evaluation, but it was very different than expected. Rather than the boss going to inventory, the boss went to accounting and had it crunch numbers to ensure the order hadn't been fulfilled. After it approved it and it went to inventory, inventory also went back to accounting to verify it's work. I don't think accounting needed to be looped in here, and it would have been simpler if inventory handled this, at least one of the times. After that finished, i did not love the response customer service generated. It was too transparent about our inventory issues, and was not very professional. But overall, the agents did work correctly. I would give this a solid rating, but it could be faster and customer service needs to be amended. 102: High marks here. This ticket was fast, and went right from the boss to facilities. That is what I predicted, and I don't think it can be made more efficient. 103: This also followed more or less what I predicted, but there were more steps than I originally thought. Inventory and accounting seem to work closely together on pricing/quantities, and there may be room to have an agent that can do both of those and limit the overlap. But this was done accurately (minus the same Customer Service issue mentioned in 101), and I think solid/high marks. I think inventory and accounting can be one agent that handles both inventory and how that number of inventory affects the overall cash, as there was lots of back and forth between those two agents. Three issues these agents could solve: How do we price a new item (Boss gave a recommendation for a discount in 103), pay the gas bill (very similar to 102), and handling simple online orders (similar to 103, but should be even more straightforward). Three issues these agents would need help on: refund requests (there is no agent that determines if an item is defective), shipping time questions (no agent that can determine how long it takes to ship something for a different location), and handling employee issues, as there is no agent that can deal with sensitive employee information.

## Problem 11

1. Thank you, last Q
2. Push the code to a public GitHub repository so it can be cloned. Give me the repo URL, and also put it in output/github_url.txt. DO NOT put my real .env to GitHub, but do include both database files. Follow the attached layout. [attached image: folder layout with hw5/ containing AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/ (campus_customs.db, campus_customs_new.db), mcp_server/ (server.py, README.md), frontend/, backend/ (main.py, models.py, prompts/ with boss.md, inventory.md, accounting.md, facilities.md, customer_service.md), output/ (harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt)]
3. We're gonna make a couple of edits. I'll tell you when to rerun Q11 and post the updated one again
4. Okay thanks. Let's redo Q11?

## Why?

Two years ago, somewhere in Stockholm, I lost my grandpas necklace. It was given to me before he passed and it was my most cherished posession, something that I meant to pass on to my kids when they were older or old enough. 

I checked with hotels, did a polisanmälan, asked help from an interdimensional seer and to this date it remains lost. A few weeks after losing it I thought maybe the person who finds it would want to sell it so i started lurking local pawnshop websites and other second hand marketplaces sure that I would find it there. I did that from time to time for many weeks but got just frustrated because of how tedious the task was.

A few weeks ago we had a workshop on AI agents at work. The workshop was framed on the implementation of agents in the corporate world. They talked about company profiles, business intelligence and such and having a team of agents facilitating this type of work and even an orchestrator agent to help managing all these agents. 

I thought, this can be more romantic; a radar, a sonar for the greatests gift. 

## What the agents does

This is intended to be an finder that queries second hand marketplaces using keywords best describing the lost object. Once the results are narrowed down it does a visual comparison of the results against references images of my grandpas necklace and other very similar items I found on the internet. Once that is done it creates an interactive (it has links!) html report showing me the ones that most resemble any of the reference images for my review. The agent keeps track of what has been shown so that in theory I don't have to review items that were shown in a previous run.

## Stack

The workshop we attended introduced the agent team in Claude Work. I am using Vibe (Mistral) coding assistant to draft the different parts of the finder.

## Status

This is a work in progress, limited mostly by the free(?) tokens Vibe gives every month.
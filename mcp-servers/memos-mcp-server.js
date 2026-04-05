#!/usr/bin/env node
"use strict";
/**
 * MemOS MCP Server — bridges OpenClaw to the MemOS REST API.
 *
 * Exposes the following MCP tools:
 *   - memos_search         — semantic memory search
 *   - memos_add            — add memories (text or chat messages)
 *   - memos_get_all        — list all memories for a user
 *   - memos_get_memory     — get specific memories with filters
 *   - memos_delete         — delete memories
 *   - memos_feedback       — provide feedback on memories
 *   - memos_chat           — chat with MemOS (retrieval-augmented)
 *
 * Environment:
 *   MEMOS_API_URL  — base URL of the MemOS API (default: http://memos-api:8000)
 *   MEMOS_USER_ID  — default user ID (default: "openclaw")
 */

const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");

const MEMOS_API_URL = process.env.MEMOS_API_URL || "http://memos-api:8000";
const DEFAULT_USER_ID = process.env.MEMOS_USER_ID || "openclaw";

// ── helpers ────────────────────────────────────────────────────────────────

async function callMemos(path, body) {
  const url = `${MEMOS_API_URL}${path}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`MemOS ${path} returned ${resp.status}: ${text}`);
  }
  return resp.json();
}

// ── server ─────────────────────────────────────────────────────────────────

const server = new Server(
  { name: "memos", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// ── tool definitions ───────────────────────────────────────────────────────

const TOOLS = [
  {
    name: "memos_search",
    description:
      "Search MemOS memories by semantic query. Returns relevant text memories, preference memories, tool memories, and skill memories. Use this to recall past knowledge, user preferences, or conversation context.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Natural-language search query",
        },
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
        top_k: {
          type: "integer",
          description: "Number of text memories to retrieve (default: 10)",
        },
        mode: {
          type: "string",
          enum: ["fast", "fine", "mixture"],
          description: "Search mode: fast (default), fine, or mixture",
        },
        search_memory_type: {
          type: "string",
          description:
            "Type of memory to search: All (default), WorkingMemory, LongTermMemory, UserMemory, PreferenceMemory, SkillMemory, etc.",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "memos_add",
    description:
      "Add new memories to MemOS. Provide either a plain text string or an array of chat messages in OpenAI format. MemOS will extract and store relevant memories automatically.",
    inputSchema: {
      type: "object",
      properties: {
        messages: {
          description:
            'Either a plain text string or an array of chat messages [{role, content}]. Text example: "User likes hiking". Message example: [{"role":"user","content":"I love hiking"},{"role":"assistant","content":"Great!"}]',
        },
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
        custom_tags: {
          type: "array",
          items: { type: "string" },
          description: "Optional tags, e.g. ['Travel', 'family']",
        },
        async_mode: {
          type: "string",
          enum: ["async", "sync"],
          description:
            "Whether to process synchronously or asynchronously (default: async)",
        },
      },
      required: ["messages"],
    },
  },
  {
    name: "memos_get_all",
    description:
      "Retrieve all memories stored for a user. Returns the full memory list. Use sparingly — prefer memos_search for targeted retrieval.",
    inputSchema: {
      type: "object",
      properties: {
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
      },
    },
  },
  {
    name: "memos_get_memory",
    description:
      "Get specific memories for a user, optionally filtered by memory type or pagination.",
    inputSchema: {
      type: "object",
      properties: {
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
        memory_type: {
          type: "string",
          description:
            "Memory type filter: All, WorkingMemory, LongTermMemory, UserMemory, PreferenceMemory, SkillMemory, etc.",
        },
        page: {
          type: "integer",
          description: "Page number (1-based)",
        },
        page_size: {
          type: "integer",
          description: "Page size (default: 20)",
        },
      },
    },
  },
  {
    name: "memos_delete",
    description: "Delete specific memories by their IDs for a user.",
    inputSchema: {
      type: "object",
      properties: {
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
        memory_ids: {
          type: "array",
          items: { type: "string" },
          description: "Array of memory IDs to delete",
        },
      },
      required: ["memory_ids"],
    },
  },
  {
    name: "memos_feedback",
    description:
      "Provide feedback on memories (e.g. upvote, downvote) to improve future recall quality.",
    inputSchema: {
      type: "object",
      properties: {
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
        memory_id: {
          type: "string",
          description: "ID of the memory to give feedback on",
        },
        feedback: {
          type: "string",
          enum: ["like", "dislike"],
          description: "Feedback type: like or dislike",
        },
      },
      required: ["memory_id", "feedback"],
    },
  },
  {
    name: "memos_chat",
    description:
      "Chat with MemOS — sends a message and gets a retrieval-augmented response that incorporates relevant memories. Good for asking questions where stored memories should inform the answer.",
    inputSchema: {
      type: "object",
      properties: {
        messages: {
          type: "array",
          items: {
            type: "object",
            properties: {
              role: {
                type: "string",
                enum: ["system", "user", "assistant"],
              },
              content: { type: "string" },
            },
            required: ["role", "content"],
          },
          description: "Chat messages in OpenAI format [{role, content}]",
        },
        user_id: {
          type: "string",
          description: `User ID (default: "${DEFAULT_USER_ID}")`,
        },
      },
      required: ["messages"],
    },
  },
];

// ── handlers ───────────────────────────────────────────────────────────────

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const userId = args?.user_id || DEFAULT_USER_ID;

  try {
    let result;

    switch (name) {
      case "memos_search": {
        result = await callMemos("/product/search", {
          query: args.query,
          user_id: userId,
          top_k: args.top_k ?? 10,
          mode: args.mode ?? "fast",
          search_memory_type: args.search_memory_type ?? "All",
        });
        break;
      }

      case "memos_add": {
        result = await callMemos("/product/add", {
          messages: args.messages,
          user_id: userId,
          custom_tags: args.custom_tags ?? [],
          async_mode: args.async_mode ?? "async",
        });
        break;
      }

      case "memos_get_all": {
        result = await callMemos("/product/get_all", {
          user_id: userId,
        });
        break;
      }

      case "memos_get_memory": {
        result = await callMemos("/product/get_memory", {
          user_id: userId,
          memory_type: args?.memory_type ?? "All",
          page: args?.page ?? 1,
          page_size: args?.page_size ?? 20,
        });
        break;
      }

      case "memos_delete": {
        result = await callMemos("/product/delete_memory", {
          user_id: userId,
          memory_ids: args.memory_ids,
        });
        break;
      }

      case "memos_feedback": {
        result = await callMemos("/product/feedback", {
          user_id: userId,
          memory_id: args.memory_id,
          feedback: args.feedback,
        });
        break;
      }

      case "memos_chat": {
        result = await callMemos("/product/chat/complete", {
          messages: args.messages,
          user_id: userId,
        });
        break;
      }

      default:
        return {
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (err) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

// ── start ──────────────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${err.message}\n`);
  process.exit(1);
});

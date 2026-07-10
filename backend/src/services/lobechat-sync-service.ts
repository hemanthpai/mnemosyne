import pg from "pg";
import type { ConversationService } from "./conversation-service.js";

const { Pool } = pg;

interface LobeMessage {
  id: string;
  role: string;
  content: string;
  created_at: Date;
}

interface LobeTopic {
  id: string;
  title: string;
  updated_at: Date;
}

export class LobeChatSyncService {
  private pool: pg.Pool;
  private intervalMs: number;
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastSyncAt: Date = new Date(0);
  private syncing = false;

  constructor(
    databaseUrl: string,
    private conversationService: ConversationService,
    intervalMs = 30_000,
  ) {
    this.pool = new Pool({ connectionString: databaseUrl });
    this.intervalMs = intervalMs;
  }

  async start(): Promise<void> {
    // Verify connectivity
    const client = await this.pool.connect();
    client.release();

    // Run initial sync immediately
    await this.sync();

    // Schedule periodic syncs
    this.timer = setInterval(() => {
      this.sync().catch((err) =>
        console.error("LobeChat sync error:", err.message),
      );
    }, this.intervalMs);
  }

  async stop(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    await this.pool.end();
  }

  private async sync(): Promise<void> {
    if (this.syncing) return;
    this.syncing = true;

    try {
      // Find topics updated since last sync
      const topicResult = await this.pool.query<LobeTopic>(
        `SELECT id, title, updated_at
         FROM topics
         WHERE updated_at > $1
         ORDER BY updated_at ASC`,
        [this.lastSyncAt.toISOString()],
      );

      if (topicResult.rows.length === 0) {
        return;
      }

      let latestUpdate = this.lastSyncAt;

      for (const topic of topicResult.rows) {
        try {
          await this.syncTopic(topic);
          if (topic.updated_at > latestUpdate) {
            latestUpdate = topic.updated_at;
          }
        } catch (err) {
          console.error(
            `LobeChat sync: failed to sync topic ${topic.id}:`,
            (err as Error).message,
          );
        }
      }

      this.lastSyncAt = latestUpdate;
      if (topicResult.rows.length > 0) {
        console.log(`LobeChat sync: synced ${topicResult.rows.length} topics`);
      }
    } finally {
      this.syncing = false;
    }
  }

  private async syncTopic(topic: LobeTopic): Promise<void> {
    const sourceId = `lobechat-topic-${topic.id}`;

    // Check how many messages we already have
    const existing =
      await this.conversationService.findBySourceId(sourceId);
    const existingCount = existing?.messages?.length ?? 0;

    // Fetch all messages for this topic, ordered by position
    const msgResult = await this.pool.query<LobeMessage>(
      `SELECT id, role, content, created_at
       FROM messages
       WHERE topic_id = $1
       ORDER BY created_at ASC`,
      [topic.id],
    );

    const allMessages = msgResult.rows.filter(
      (m) => m.content && m.content.trim() !== "",
    );

    // Only send new messages (append-only)
    const newMessages = allMessages.slice(existingCount);
    if (newMessages.length === 0 && existing) {
      return; // Nothing new to sync
    }

    const messages = newMessages.map((m) => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: m.content,
    }));

    await this.conversationService.upsert(sourceId, {
      title: topic.title || "Untitled",
      source: "lobechat",
      tags: ["lobechat", "synced"],
      messages: messages.length > 0 ? messages : undefined,
    });
  }
}

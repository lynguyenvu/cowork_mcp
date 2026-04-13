import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  type WASocket,
  type ConnectionState,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import qrcodeTerminal from 'qrcode-terminal';
import { AUTH_BASE_DIR, RECONNECT_DELAY_MS, MAX_RECONNECT_ATTEMPTS } from './constants.js';
import { getStore, deleteStore, type MessageStore } from './store.js';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'qr_pending';

export interface WhatsAppStatus {
  accountId: string;
  status: ConnectionStatus;
  qrCode: string | null;
  phoneNumber: string | null;
  isLoggedIn: boolean;
}

/** Per-account WhatsApp connection manager */
export class WhatsAppManager {
  private sock: WASocket | null = null;
  private connectionStatus: ConnectionStatus = 'disconnected';
  private qrCode: string | null = null;
  private phoneNumber: string | null = null;
  private reconnectAttempts = 0;
  private isShuttingDown = false;

  /** Silent pino logger — writes to stderr only to avoid polluting stdio MCP transport */
  private logger = pino({ level: 'silent' });

  constructor(private readonly accountId: string) {}

  /** Auth directory for this account's credentials */
  private get authDir(): string {
    return `${AUTH_BASE_DIR}/${this.accountId}`;
  }

  /** In-memory store for this account */
  getStore(): MessageStore {
    return getStore(this.accountId);
  }

  async init(): Promise<void> {
    if (this.sock) return;
    await this.connect();
  }

  private async connect(): Promise<void> {
    this.connectionStatus = 'connecting';
    this.qrCode = null;
    const tag = `[WhatsApp:${this.accountId}]`;

    try {
      const { state, saveCreds } = await useMultiFileAuthState(this.authDir);
      const { version } = await fetchLatestBaileysVersion();

      this.sock = makeWASocket({
        version,
        logger: this.logger,
        printQRInTerminal: false,
        auth: {
          creds: state.creds,
          keys: makeCacheableSignalKeyStore(state.keys, this.logger),
        },
        generateHighQualityLinkPreview: true,
        syncFullHistory: false,
        markOnlineOnConnect: false,
      });

      this.sock.ev.on('creds.update', saveCreds);

      this.sock.ev.on('connection.update', async (update: Partial<ConnectionState>) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
          this.qrCode = qr;
          this.connectionStatus = 'qr_pending';
          process.stderr.write(`\n${tag} Scan QR code with WhatsApp:\n\n`);
          qrcodeTerminal.generate(qr, { small: true }, (qrAscii: string) => {
            process.stderr.write(qrAscii + '\n\n');
          });
        }

        if (connection === 'open') {
          this.connectionStatus = 'connected';
          this.qrCode = null;
          this.reconnectAttempts = 0;
          const jid = this.sock?.user?.id ?? null;
          this.phoneNumber = jid ? jid.split(':')[0].split('@')[0] : null;
          process.stderr.write(`${tag} Connected as ${this.phoneNumber}\n`);
        }

        if (connection === 'close') {
          const boom = lastDisconnect?.error as Boom | undefined;
          const statusCode = boom?.output?.statusCode;
          const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

          process.stderr.write(
            `${tag} Connection closed, code=${statusCode}, reconnect=${shouldReconnect}\n`
          );

          this.sock = null;
          this.connectionStatus = 'disconnected';
          this.phoneNumber = null;

          if (shouldReconnect && !this.isShuttingDown) {
            if (this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
              this.reconnectAttempts++;
              process.stderr.write(
                `${tag} Reconnecting in ${RECONNECT_DELAY_MS}ms (attempt ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...\n`
              );
              setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
            } else {
              process.stderr.write(`${tag} Max reconnect attempts reached. Please restart.\n`);
            }
          }
        }
      });

      // ── Populate per-account message store ─────────────────────────────────
      const s = this.getStore();

      this.sock.ev.on('messages.upsert', ({ messages, type }) => {
        for (const msg of messages) {
          const jid = msg.key.remoteJid;
          if (!jid) continue;
          // Store each message to SQLite with accountId
          s.storeMessage(this.accountId, {
            key: msg.key,
            message: msg.message,
            messageTimestamp: msg.messageTimestamp,
            pushName: msg.pushName,
            broadcast: msg.broadcast,
          });
        }
      });

      this.sock.ev.on('chats.upsert', (chats) => {
        s.upsertChats(
          chats.map((c) => ({
            id: c.id,
            name: c.name ?? undefined,
            unreadCount: c.unreadCount,
            conversationTimestamp: c.conversationTimestamp,
          }))
        );
      });

      this.sock.ev.on('chats.update', (updates) => {
        for (const update of updates) s.updateChat(update);
      });
    } catch (err) {
      this.connectionStatus = 'disconnected';
      process.stderr.write(`${tag} Connection error: ${String(err)}\n`);
      throw err;
    }
  }

  /** Get the active socket — throws if not connected */
  getSock(): WASocket {
    if (!this.sock) {
      throw new Error(
        `WhatsApp account "${this.accountId}" not connected. ` +
          `Use whatsapp_get_status to check status and QR code.`
      );
    }
    return this.sock;
  }

  getStatus(): WhatsAppStatus {
    return {
      accountId: this.accountId,
      status: this.connectionStatus,
      qrCode: this.qrCode,
      phoneNumber: this.phoneNumber,
      isLoggedIn: this.connectionStatus === 'connected',
    };
  }

  async logout(): Promise<void> {
    this.isShuttingDown = true;
    if (this.sock) {
      try { await this.sock.logout(); } catch { /* ignore */ }
      this.sock = null;
    }
    this.connectionStatus = 'disconnected';
    this.qrCode = null;
    this.phoneNumber = null;
    deleteStore(this.accountId);

    const { rm } = await import('fs/promises');
    try { await rm(this.authDir, { recursive: true, force: true }); } catch { /* ignore */ }

    this.isShuttingDown = false;
    this.reconnectAttempts = 0;

    // Reconnect to generate new QR for fresh login
    await this.connect();
  }
}

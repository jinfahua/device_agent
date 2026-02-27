/**
 * Python Bridge - RPC communication with Device Agent
 *
 * Manages the Python subprocess and handles JSON-RPC communication.
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";

export interface BridgeOptions {
  pythonPath?: string;
  modulePath?: string;
}

export interface RPCRequest {
  id: string;
  tool: string;
  input: Record<string, unknown>;
}

export interface RPCResponse {
  id: string;
  success: boolean;
  data?: unknown;
  error?: string;
}

/**
 * Bridge to Python Device Agent via JSON-RPC over stdin/stdout
 */
export class PythonBridge extends EventEmitter {
  private pythonPath: string;
  private modulePath: string | undefined;
  private process: ChildProcess | null = null;
  private requestQueue: Map<string, { resolve: Function; reject: Function }> = new Map();
  private messageBuffer: string = "";
  private requestId: number = 0;

  constructor(options: BridgeOptions = {}) {
    super();
    this.pythonPath = options.pythonPath || "python";
    this.modulePath = options.modulePath;
  }

  /**
   * Start the Python RPC server
   */
  async start(): Promise<void> {
    const args = this.modulePath
      ? ["-m", this.modulePath]
      : ["-m", "device_agent.rpc_server"];

    this.process = spawn(this.pythonPath, args, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    // Handle stdout for responses
    this.process.stdout?.on("data", (data: Buffer) => {
      this.messageBuffer += data.toString();
      this.processBuffer();
    });

    // Handle stderr for logging
    this.process.stderr?.on("data", (data: Buffer) => {
      const message = data.toString().trim();
      if (message) {
        console.error(`[Device Agent] ${message}`);
      }
    });

    // Handle process exit
    this.process.on("exit", (code) => {
      this.emit("exit", code);
      // Reject pending requests
      for (const [id, { reject }] of this.requestQueue) {
        reject(new Error(`Python process exited (code: ${code})`));
      }
      this.requestQueue.clear();
    });

    // Wait for server to be ready
    await this.waitForReady();
  }

  /**
   * Stop the Python RPC server
   */
  async stop(): Promise<void> {
    if (this.process) {
      // Send shutdown signal
      this.process.stdin?.write(JSON.stringify({ method: "shutdown" }) + "\n");

      // Give it a moment to shut down gracefully
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Force kill if still running
      if (!this.process.killed) {
        this.process.kill();
      }

      this.process = null;
    }
  }

  /**
   * Call a tool on the Python side
   */
  async callTool(toolName: string, inputData: Record<string, unknown>): Promise<unknown> {
    if (!this.process || this.process.killed) {
      throw new Error("Python bridge not started");
    }

    const id = this.nextRequestId();
    const request: RPCRequest = {
      id,
      tool: toolName,
      input: inputData,
    };

    return new Promise((resolve, reject) => {
      this.requestQueue.set(id, { resolve, reject });

      // Send request
      this.process!.stdin!.write(JSON.stringify(request) + "\n");

      // Timeout after 30 seconds
      setTimeout(() => {
        if (this.requestQueue.has(id)) {
          this.requestQueue.delete(id);
          reject(new Error(`Request timeout for tool: ${toolName}`));
        }
      }, 30000);
    });
  }

  /**
   * Check if bridge is connected
   */
  isConnected(): boolean {
    return this.process !== null && !this.process.killed;
  }

  private nextRequestId(): string {
    return `${++this.requestId}`;
  }

  private processBuffer(): void {
    const lines = this.messageBuffer.split("\n");
    this.messageBuffer = lines.pop() || ""; // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.trim()) {
        try {
          const response: RPCResponse = JSON.parse(line);
          this.handleResponse(response);
        } catch (e) {
          console.error("Failed to parse response:", line);
        }
      }
    }
  }

  private handleResponse(response: RPCResponse): void {
    const pending = this.requestQueue.get(response.id);
    if (pending) {
      this.requestQueue.delete(response.id);
      if (response.success) {
        pending.resolve(response.data);
      } else {
        pending.reject(new Error(response.error || "Unknown error"));
      }
    }
  }

  private async waitForReady(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error("Timeout waiting for Python server to start"));
      }, 10000);

      const checkReady = () => {
        this.callTool("ping", {})
          .then(() => {
            clearTimeout(timeout);
            resolve();
          })
          .catch(() => {
            setTimeout(checkReady, 100);
          });
      };

      setTimeout(checkReady, 500);
    });
  }
}

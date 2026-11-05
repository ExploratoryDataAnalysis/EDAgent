import { apiClient } from './apiClient';
import { APIResponse, ChatMessage, ChatResponse, UUID } from '../types';

export const chatService = {
  async sendMessage(
    sessionId: UUID,
    message: string,
    history: ChatMessage[] = []
  ): Promise<ChatResponse> {
    const res = await apiClient.post<APIResponse<ChatResponse>>('/chat/message', {
      session_id: sessionId,
      message,
      conversation_history: history,
    });
    return res.data.data!;
  },
};

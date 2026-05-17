import type { Task, TaskStore } from './index.ts'

const TERMINAL_TASK_STATUSES = new Set(['SUCCESS', 'FAILED', 'CANCELLED', 'FAILD'])

function buildPersistedTask(task: Task): Task {
  return {
    ...task,
    markdown: '',
    transcript: {
      full_text: '',
      language: '',
      raw: null,
      segments: [],
    },
    audioMeta: {
      ...task.audioMeta,
      raw_info: null,
    },
  }
}

export function buildPersistedTaskState(
  state: TaskStore
): Pick<TaskStore, 'tasks' | 'currentTaskId' | 'selectedTaskId'> {
  return {
    currentTaskId: state.currentTaskId,
    selectedTaskId: state.selectedTaskId,
    tasks: state.tasks
      .filter(task => !TERMINAL_TASK_STATUSES.has(task.status))
      .map(buildPersistedTask),
  }
}

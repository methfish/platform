import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, Circle } from 'lucide-react';
import { LearnedLesson } from '../../types/agent';
import { formatDate } from '../../utils/formatters';

interface LessonsTableProps {
  lessons: LearnedLesson[];
  isLoading: boolean;
}

const SEVERITY_COLORS: Record<string, string> = {
  LOW: 'bg-green-500/15 text-green-400 border-green-500/30',
  MEDIUM: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  HIGH: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  CRITICAL: 'bg-red-500/15 text-red-400 border-red-500/30',
};

const CATEGORY_COLORS: Record<string, string> = {
  default: 'bg-surface-overlay text-gray-300 border-surface-border',
};

function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? CATEGORY_COLORS.default;
}

export default function LessonsTable({ lessons, isLoading }: LessonsTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <span className="ml-3 text-gray-400 text-sm">Loading lessons...</span>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-200">Learned Lessons</h3>
        <span className="text-xs text-gray-500">{lessons.length} lessons</span>
      </div>

      {lessons.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500 text-sm">No lessons recorded yet</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="table-header w-8" />
                <th className="table-header">Title</th>
                <th className="table-header">Category</th>
                <th className="table-header">Severity</th>
                <th className="table-header">Symbol</th>
                <th className="table-header">Applied</th>
                <th className="table-header">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {lessons.map((lesson) => {
                const isExpanded = expandedIds.has(lesson.lesson_id);
                return (
                  <LessonRow
                    key={lesson.lesson_id}
                    lesson={lesson}
                    isExpanded={isExpanded}
                    onToggle={() => toggleExpand(lesson.lesson_id)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface LessonRowProps {
  lesson: LearnedLesson;
  isExpanded: boolean;
  onToggle: () => void;
}

function LessonRow({ lesson, isExpanded, onToggle }: LessonRowProps) {
  return (
    <>
      <tr
        className="hover:bg-surface-overlay/50 transition-colors cursor-pointer"
        onClick={onToggle}
      >
        {/* Expand chevron */}
        <td className="table-cell">
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-gray-500" />
          )}
        </td>

        {/* Title */}
        <td className="table-cell">
          <span className="text-xs font-medium text-gray-200">{lesson.title}</span>
        </td>

        {/* Category */}
        <td className="table-cell">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border ${getCategoryColor(lesson.category)}`}
          >
            {lesson.category}
          </span>
        </td>

        {/* Severity */}
        <td className="table-cell">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border ${
              SEVERITY_COLORS[lesson.severity] ?? SEVERITY_COLORS.LOW
            }`}
          >
            {lesson.severity}
          </span>
        </td>

        {/* Symbol */}
        <td className="table-cell">
          <span className="text-xs text-gray-400 font-mono">
            {lesson.symbol ?? '--'}
          </span>
        </td>

        {/* Applied */}
        <td className="table-cell">
          {lesson.applied ? (
            <CheckCircle2 className="h-4 w-4 text-green-400" />
          ) : (
            <Circle className="h-4 w-4 text-gray-600" />
          )}
        </td>

        {/* Date */}
        <td className="table-cell">
          <span className="text-[11px] text-gray-400">
            {formatDate(lesson.created_at)}
          </span>
        </td>
      </tr>

      {/* Expanded detail row */}
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-4 pb-4 pt-1">
            <div className="bg-surface-base rounded-lg p-4 space-y-3 ml-6 border border-surface-border/50">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1">
                  Description
                </p>
                <p className="text-xs text-gray-300 leading-relaxed">
                  {lesson.description}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1">
                  Root Cause
                </p>
                <p className="text-xs text-gray-300 leading-relaxed">
                  {lesson.root_cause}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1">
                  Recommendation
                </p>
                <p className="text-xs text-gray-300 leading-relaxed">
                  {lesson.recommendation}
                </p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

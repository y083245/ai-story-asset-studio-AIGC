"use client";
import { useState, useCallback, useMemo } from "react";
import { uploadNovel } from "@/shared/api/novels";
import type { NovelIntakeResponse } from "@/shared/types";

const MIN_WORD_COUNT = 1000;
const MAX_WORD_COUNT = 10000;
const ALLOWED_EXTENSIONS = [".txt", ".docx"];

function countChineseChars(text: string): number {
  const chineseRegex = /[一-鿿㐀-䶿]/g;
  const matches = text.match(chineseRegex);
  return matches ? matches.length : 0;
}

function getExtension(filename: string): string {
  const lastDot = filename.lastIndexOf(".");
  if (lastDot === -1) return "";
  return filename.slice(lastDot).toLowerCase();
}

export function useNovelUpload() {
  const [novel, setNovel] = useState<NovelIntakeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentText, setCurrentText] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const wordCount = useMemo(() => countChineseChars(currentText), [currentText]);

  const reset = useCallback(() => {
    setNovel(null);
    setLoading(false);
    setError(null);
    setCurrentText("");
    setValidationError(null);
  }, []);

  const uploadText = useCallback(
    async (projectId: string, text: string): Promise<NovelIntakeResponse | null> => {
      setValidationError(null);
      setError(null);

      // Validate text is not empty
      if (!text || text.trim().length === 0) {
        setValidationError("请提供小说正文内容");
        return null;
      }

      // Validate word count
      const count = countChineseChars(text);
      setCurrentText(text);
      if (count < MIN_WORD_COUNT) {
        setValidationError(
          `字数不足：当前 ${count} 字，需要至少 ${MIN_WORD_COUNT} 字`
        );
        return null;
      }
      if (count > MAX_WORD_COUNT) {
        setValidationError(
          `字数超出：当前 ${count} 字，上限为 ${MAX_WORD_COUNT} 字`
        );
        return null;
      }

      setLoading(true);
      try {
        const result = await uploadNovel(projectId, {
          input_type: "text",
          text,
        });
        setNovel(result);
        setCurrentText(text);
        return result;
      } catch (e) {
        const message = e instanceof Error ? e.message : "上传失败，请重试";
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const uploadFile = useCallback(
    async (
      projectId: string,
      file: File
    ): Promise<NovelIntakeResponse | null> => {
      setValidationError(null);
      setError(null);

      // Validate file type
      const ext = getExtension(file.name);
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        if (ext === ".pdf") {
          setValidationError("不支持 PDF 格式，请使用 .txt 或 .docx 文件");
        } else {
          setValidationError(
            `不支持的文件格式：${ext || "未知"}，请使用 .txt 或 .docx 文件`
          );
        }
        return null;
      }

      // Read file content
      setLoading(true);
      try {
        const text = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.onerror = () => reject(new Error("文件读取失败"));
          reader.readAsText(file);
        });

        // Validate word count on file content
        const count = countChineseChars(text);
        setCurrentText(text);
        if (count < MIN_WORD_COUNT) {
          setValidationError(
            `字数不足：当前 ${count} 字，需要至少 ${MIN_WORD_COUNT} 字`
          );
          setLoading(false);
          return null;
        }
        if (count > MAX_WORD_COUNT) {
          setValidationError(
            `字数超出：当前 ${count} 字，上限为 ${MAX_WORD_COUNT} 字`
          );
          setLoading(false);
          return null;
        }

        const inputType = ext === ".docx" ? "docx" as const : "txt" as const;
        const result = await uploadNovel(projectId, {
          input_type: inputType,
          text,
        });
        setNovel(result);
        return result;
      } catch (e) {
        const message = e instanceof Error ? e.message : "上传失败，请重试";
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return {
    novel,
    loading,
    error,
    wordCount,
    validationError,
    currentText,
    uploadText,
    uploadFile,
    reset,
  };
}

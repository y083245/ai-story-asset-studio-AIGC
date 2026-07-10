import type {
  AnalysisResponse,
  CharacterListResponse,
  NovelDetailResponse,
  NovelIntakeResponse,
  ProjectCopyResponse,
  ProjectListResponse,
  ProjectResponse,
  ProjectStatusResponse,
  PropListResponse,
  SceneListResponse,
  StoryBibleResponse,
  StoryBibleVersionListResponse,
} from "@/shared/types";

const now = new Date().toISOString();

export const mockProjects: ProjectResponse[] = [
  {
    project_id: "proj-asset-001",
    user_id: "mock-user",
    title: "旧怀表",
    status: "analysis_confirmed",
    aspect_ratio: "9:16",
    style_mode: "auto",
    manual_style: "",
    generation_mode: "fast_preview",
    progress: 72,
    created_at: now,
    updated_at: now,
  },
  {
    project_id: "proj-asset-002",
    user_id: "mock-user",
    title: "雨夜书店",
    status: "generating_assets",
    aspect_ratio: "16:9",
    style_mode: "manual",
    manual_style: "都市写实视觉",
    generation_mode: "high_quality",
    progress: 46,
    created_at: now,
    updated_at: now,
  },
];

export function getMockProjectList(): ProjectListResponse {
  const items = mockProjects.filter((project) => project.status !== "archived");
  return { items, total: items.length };
}

export function getMockProject(id: string): ProjectResponse | undefined {
  return mockProjects.find((project) => project.project_id === id);
}

export function getMockWorkflowStatus(projectId: string): ProjectStatusResponse {
  const project = getMockProject(projectId);
  const status = project?.status ?? "analysis_confirmed";
  const running = status === "generating_assets";
  const workflowStatus = status === "analysis_confirmed" ? "completed" : status;
  return {
    project_id: projectId,
    status: workflowStatus,
    progress: running ? 46 : 100,
    current_stage: running ? "generating_assets" : "completed",
    message: running ? "正在生成角色、场景和道具参考图。" : "分析已完成，可以生成视觉资产。",
    stage_index: running ? 5 : 8,
    total_stages: running ? 6 : 8,
    tasks: running
      ? [
          task("parse_novel", "解析小说", "success"),
          task("clean_text", "清洗文本", "success"),
          task("detect_genre", "识别风格", "success"),
          task("extract_assets", "提取角色/场景/道具", "success"),
          task("build_story_bible", "生成视觉设定", "success"),
          task("generate_assets", "生成资产图", "running"),
        ]
      : [
          task("parse_novel", "解析小说", "success"),
          task("clean_text", "清洗文本", "success"),
          task("detect_genre", "识别风格", "success"),
          task("extract_characters", "提取角色", "success"),
          task("extract_scenes", "提取场景", "success"),
          task("extract_props", "提取道具", "success"),
          task("build_story_bible", "生成视觉设定", "success"),
          task("publish_analysis", "发布分析结果", "success"),
        ],
  };
}

function task(task_id: string, name: string, state: ProjectStatusResponse["tasks"][number]["state"]) {
  return {
    task_id,
    name,
    state,
    progress: state === "success" ? 100 : state === "running" ? 55 : 0,
    retry_count: 0,
    max_retries: 2,
  };
}

export function getMockNovelData(projectId: string): NovelIntakeResponse {
  const title = getMockProject(projectId)?.title || "未命名小说";
  const clean_text = "她在雨夜推开旧宅木门，案上那枚裂纹怀表仍停在十年前的时间。";
  return {
    novel_id: `novel-${projectId}`,
    title,
    clean_text,
    word_count: clean_text.length,
    chapter_list: [{ title: "第一章", start: 0 }],
    paragraph_list: [clean_text],
    text_chunks: [
      {
        id: "chunk-001",
        chunk_index: 0,
        content: clean_text,
        start_char: 0,
        end_char: clean_text.length,
        word_count: clean_text.length,
      },
    ],
    preprocess_report: {
      original_word_count: clean_text.length,
      clean_word_count: clean_text.length,
      ads_removed: 0,
      page_numbers_removed: 0,
      garbled_lines_removed: 0,
      blank_lines_removed: 0,
      encoding_detected: "utf-8",
      input_type: "text",
    },
  };
}

export function getMockNovelDetail(projectId: string): NovelDetailResponse {
  const data = getMockNovelData(projectId);
  return {
    id: data.novel_id,
    project_id: projectId,
    title: data.title,
    word_count: data.word_count,
    clean_text: data.clean_text,
    chapter_list: { chapters: data.chapter_list },
    paragraph_list: data.paragraph_list,
    status: "ready",
    created_at: now,
    updated_at: now,
  };
}

export function getMockAnalysis(projectId: string): AnalysisResponse {
  return {
    project_id: projectId,
    genre: "都市悬疑",
    visual_style: "都市写实视觉",
    style_confidence: 0.92,
    story_summary: "一枚停摆怀表把女主带回旧宅秘密，她需要从角色、空间和关键道具中还原真相。",
    main_conflict: "女主寻找怀表来源，同时面对家族旧事与现实身份冲突。",
    protagonist: {
      character_id: "CH_001",
      name: "林雨眠",
      role: "protagonist",
      description: "二十六岁，冷静克制，黑色短发，常穿米白风衣。",
      gender: "女",
      age_range: "26岁",
    },
    emotional_tone: "克制、悬疑、带一点怀旧感",
    world_setting: "现代城市与旧宅空间并置",
    time_period: "当代",
    color_palette: ["冷灰", "旧金", "雨夜蓝", "米白"],
    composition_language: ["正面全身角色参考", "无人空场景", "纯白背景道具单品图"],
    characters: getMockCharacters(projectId).characters.map((character) => ({
      character_id: character.character_id,
      name: character.name,
      role: character.role,
      description: character.description,
      gender: character.gender,
      age_range: character.age_range,
    })),
    scenes: getMockScenes(projectId).scenes.map((scene) => ({
      scene_id: scene.scene_id,
      name: scene.name,
      description: scene.description,
      time_period: scene.time_period,
      mood: scene.mood,
      fixed_anchors: scene.fixed_anchors,
    })),
    props: getMockProps(projectId).props.map((prop) => ({
      prop_id: prop.prop_id,
      name: prop.name,
      description: prop.description,
      function: prop.function,
      state_timeline: prop.state_timeline,
    })),
  };
}

export function getMockStoryBible(projectId: string): StoryBibleResponse {
  const analysis = getMockAnalysis(projectId);
  return {
    ...analysis,
    version: 1,
    title: getMockProject(projectId)?.title || "未命名小说",
    aspect_ratio: getMockProject(projectId)?.aspect_ratio || "9:16",
    negative_prompt_rules: [
      { category: "通用", terms: ["水印", "logo", "文字标识", "多余人物"], reason: "保证资产图干净可复用" },
    ],
    created_at: now,
    updated_at: now,
  };
}

export function getMockStoryBibleVersions(projectId: string): StoryBibleVersionListResponse {
  return {
    project_id: projectId,
    versions: [{ version: 1, created_at: now, title: getMockProject(projectId)?.title || "视觉设定" }],
  };
}

export function getMockCharacters(projectId: string): CharacterListResponse {
  return {
    characters: [
      {
        id: `char-db-001-${projectId}`,
        project_id: projectId,
        character_id: "CH_001",
        name: "林雨眠",
        description: "二十六岁女性，黑色短发，神情冷静，做事谨慎。",
        role: "protagonist",
        gender: "女",
        age_range: "26岁",
        outfit: "米白色长风衣，深灰针织衫，黑色直筒裤，低跟短靴。",
        avatar_url: undefined,
        reference_asset_ids: [],
        reference_image_urls: [],
        is_locked: false,
        created_at: now,
        updated_at: now,
      },
      {
        id: `char-db-002-${projectId}`,
        project_id: projectId,
        character_id: "CH_002",
        name: "顾沉",
        description: "三十二岁男性，眉眼锋利，深色西装，气质疏离。",
        role: "supporting",
        gender: "男",
        age_range: "32岁",
        outfit: "深炭灰修身西装，白色衬衫，黑色皮鞋，银色腕表。",
        avatar_url: undefined,
        reference_asset_ids: [],
        reference_image_urls: [],
        is_locked: false,
        created_at: now,
        updated_at: now,
      },
    ],
    total: 2,
  };
}

export function getMockScenes(projectId: string): SceneListResponse {
  return {
    scenes: [
      {
        id: `scene-db-001-${projectId}`,
        project_id: projectId,
        scene_id: "SC_001",
        name: "雨夜旧宅玄关",
        description: "老式木门、青灰石砖、昏黄壁灯、潮湿雨痕构成的无人旧宅入口。",
        time_period: "夜晚",
        mood: "潮湿、压抑、怀旧",
        location: "室内",
        fixed_anchors: ["深色木门", "青灰石砖地面", "昏黄壁灯", "旧伞架"],
        thumbnail_url: undefined,
        is_locked: false,
        created_at: now,
        updated_at: now,
      },
      {
        id: `scene-db-002-${projectId}`,
        project_id: projectId,
        scene_id: "SC_002",
        name: "冷白灯档案室",
        description: "金属档案柜、冷白顶灯、长桌和玻璃隔断组成的无人档案室。",
        time_period: "深夜",
        mood: "理性、冷峻、紧张",
        location: "室内",
        fixed_anchors: ["金属档案柜", "冷白顶灯", "长条工作桌", "磨砂玻璃隔断"],
        thumbnail_url: undefined,
        is_locked: false,
        created_at: now,
        updated_at: now,
      },
    ],
    total: 2,
  };
}

export function getMockProps(projectId: string): PropListResponse {
  return {
    props: [
      {
        id: `prop-db-001-${projectId}`,
        project_id: projectId,
        prop_id: "PR_001",
        name: "裂纹怀表",
        description: "旧金色金属怀表，表盖有细裂纹，内侧夹着一张泛黄照片。",
        function: "贯穿故事的核心信物。",
        state_timeline: ["在旧宅案上被发现", "打开后露出照片", "成为确认身份的证据"],
        thumbnail_url: undefined,
        is_locked: false,
        created_at: now,
        updated_at: now,
      },
      {
        id: `prop-db-002-${projectId}`,
        project_id: projectId,
        prop_id: "PR_002",
        name: "旧档案袋",
        description: "牛皮纸档案袋，边角磨损，封口处有蓝色印章痕迹。",
        function: "提供人物关系和旧事线索。",
        state_timeline: ["被放在档案室长桌上", "封口被拆开", "资料被重新整理"],
        thumbnail_url: undefined,
        is_locked: false,
        created_at: now,
        updated_at: now,
      },
    ],
    total: 2,
  };
}

export function getMockProjectCopy(projectId: string): ProjectCopyResponse {
  const original = getMockProject(projectId);
  if (!original) throw new Error("Project not found");
  const copy: ProjectResponse = {
    ...original,
    project_id: `proj-copy-${Date.now()}`,
    title: `${original.title} (副本)`,
    status: "draft",
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  mockProjects.unshift(copy);
  return { original_id: projectId, new_project: copy };
}

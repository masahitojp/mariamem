CREATE TABLE `User` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(191) NOT NULL,
  `name` VARCHAR(120) NULL,
  UNIQUE INDEX `User_email_key` (`email`),
  PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE TABLE `Post` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(191) NOT NULL,
  `authorId` INTEGER NOT NULL,
  `amount` DECIMAL(20,6) NOT NULL,
  `big` BIGINT NOT NULL,
  `at` DATETIME(3) NOT NULL,
  `meta` JSON NOT NULL,
  `blob` LONGBLOB NOT NULL,
  INDEX `Post_authorId_idx` (`authorId`),
  PRIMARY KEY (`id`),
  CONSTRAINT `Post_authorId_fkey` FOREIGN KEY (`authorId`) REFERENCES `User` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

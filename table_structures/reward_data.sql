-- phpMyAdmin SQL Dump
-- version 4.1.14
-- http://www.phpmyadmin.net
--
-- Host: 127.0.0.1
-- Generation Time: Mar 01, 2022 at 11:13 PM
-- Server version: 5.6.17
-- PHP Version: 5.5.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `ema`
--

-- --------------------------------------------------------

--
-- Table structure for table `reward_data`
--

CREATE TABLE IF NOT EXISTS `reward_data` (
  `speakerID` varchar(500) NOT NULL DEFAULT '9',
  `empathid` varchar(50) NOT NULL,
  `TimeSent` datetime(6) DEFAULT NULL,
  `suid` varchar(20) DEFAULT NULL,
  `TimeReceived` datetime(6) DEFAULT NULL,
  `Response` varchar(40) DEFAULT NULL,
  `Question` varchar(5000) DEFAULT NULL,
  `QuestionType` varchar(200) DEFAULT NULL,
  `QuestionName` varchar(500) DEFAULT NULL,
  `Reactive` int(100) NOT NULL DEFAULT '0',
  `SentTimes` int(100) NOT NULL DEFAULT '0',
  `ConnectionError` int(100) NOT NULL DEFAULT '0',
  `Uploaded` int(20) NOT NULL,
  PRIMARY KEY (`empathid`),
  UNIQUE KEY `empathid_UNIQUE` (`empathid`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
